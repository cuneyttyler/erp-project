"""Tests for the home-panel widget data endpoint: gating, that every
registered widget computes on an empty tenant, and the figures behind the
finance widgets a user will actually read off the panel."""

import datetime
from decimal import Decimal

from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import Account, Bill, BillLine, Entity, Invoice, InvoiceLine, JournalEntry, JournalLine, Party, Payment, User
from apps.inventory.models import StockMove, Warehouse
from apps.core.models import Item
from apps.plugins import registry
from apps.plugins.models import PluginState
from apps.plugins.periods import month_key, month_start

HOST = {"HTTP_HOST": "tenant.test.com"}
ALL_PACKAGES = [p.package for p in registry.PLUGINS if p.package]


class WidgetTestBase(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="user", password="x")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.tenant.active_packages = ALL_PACKAGES
        self.tenant.save()
        self.today = timezone.localdate()

    def data(self, key, **params):
        response = self.client.get(f"/api/v1/plugins/widgets/{key}/data/", params, **HOST)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data


class WidgetGatingTests(WidgetTestBase):
    def test_unknown_widget_is_404(self):
        self.assertEqual(self.client.get("/api/v1/plugins/widgets/nope/data/", **HOST).status_code, 404)

    def test_widget_of_an_unlicensed_package_is_403(self):
        self.tenant.active_packages = []
        self.tenant.save()
        self.assertEqual(self.client.get("/api/v1/plugins/widgets/low_stock/data/", **HOST).status_code, 403)

    def test_widget_of_a_removed_plugin_is_403(self):
        PluginState.objects.create(key="general_ledger", is_enabled=False)
        self.assertEqual(self.client.get("/api/v1/plugins/widgets/cash_position/data/", **HOST).status_code, 403)

    def test_non_integer_entity_is_400(self):
        self.assertEqual(self.client.get("/api/v1/plugins/widgets/cash_position/data/", {"entity": "x"}, **HOST).status_code, 400)


class EveryWidgetTests(WidgetTestBase):
    def test_every_widget_computes_on_an_empty_tenant(self):
        for widget in registry.all_widgets():
            with self.subTest(widget=widget.key):
                payload = self.data(widget.key)
                self.assertEqual(payload["kind"], widget.kind)

    def test_chart_series_share_one_label_axis(self):
        for widget in registry.all_widgets():
            if widget.kind != registry.CHART:
                continue
            with self.subTest(widget=widget.key):
                labels = [[p["label"] for p in s["points"]] for s in self.data(widget.key)["series"]]
                self.assertTrue(all(axis == labels[0] for axis in labels))


class LedgerWidgetTests(WidgetTestBase):
    def setUp(self):
        super().setUp()
        self.entity = Entity.objects.create(name="A", code="A")
        self.other_entity = Entity.objects.create(name="B", code="B")
        self.accounts = {
            code: Account.objects.create(entity=self.entity, code=code, name=code, account_type=account_type)
            for code, account_type in [("100", Account.ASSET), ("600", Account.REVENUE), ("770", Account.EXPENSE)]
        }

    def post(self, date, debit_code, credit_code, amount, status=JournalEntry.POSTED):
        entry = JournalEntry.objects.create(entity=self.entity, date=date, status=status)
        JournalLine.objects.create(journal_entry=entry, account=self.accounts[debit_code], debit=amount)
        JournalLine.objects.create(journal_entry=entry, account=self.accounts[credit_code], credit=amount)
        return entry

    def test_cash_position_is_the_running_posted_cash_balance(self):
        last_month = month_start(self.today, 1)
        self.post(last_month, "100", "600", Decimal("1000"))
        self.post(self.today, "770", "100", Decimal("300"))
        self.post(self.today, "100", "600", Decimal("999"), status=JournalEntry.DRAFT)  # not posted: ignored

        payload = self.data("cash_position")
        self.assertEqual(Decimal(payload["value"]), Decimal("700"))
        self.assertEqual([Decimal(p["value"]) for p in payload["trend"][-2:]], [Decimal("1000"), Decimal("700")])
        self.assertEqual(Decimal(payload["secondary"][0]["value"]), Decimal("-300"))

    def test_cash_position_includes_balances_older_than_the_trend_window(self):
        self.post(month_start(self.today, 24), "100", "600", Decimal("500"))
        payload = self.data("cash_position")
        self.assertEqual(Decimal(payload["value"]), Decimal("500"))
        self.assertEqual(Decimal(payload["trend"][0]["value"]), Decimal("500"))

    def test_month_to_date_figures_and_delta(self):
        last_month = month_start(self.today, 1)
        self.post(last_month, "100", "600", Decimal("1000"))
        self.post(self.today, "100", "600", Decimal("1500"))
        self.post(self.today, "770", "100", Decimal("400"))

        revenue = self.data("revenue_mtd")
        self.assertEqual(Decimal(revenue["value"]), Decimal("1500"))
        self.assertEqual(Decimal(revenue["delta"]["percent"]), Decimal("50.0"))
        self.assertEqual(Decimal(self.data("expenses_mtd")["value"]), Decimal("400"))
        self.assertEqual(Decimal(self.data("net_income_mtd")["value"]), Decimal("1100"))

    def test_no_delta_without_a_previous_month_figure(self):
        self.post(self.today, "100", "600", Decimal("1500"))
        self.assertIsNone(self.data("revenue_mtd")["delta"])

    def test_trend_chart_ends_on_the_current_month(self):
        self.post(self.today, "100", "600", Decimal("1500"))
        revenue, expenses = self.data("revenue_expense_trend")["series"]
        self.assertEqual(len(revenue["points"]), 12)
        self.assertEqual(revenue["points"][-1], {"label": month_key(self.today), "value": "1500.00"})
        self.assertEqual(Decimal(expenses["points"][-1]["value"]), Decimal("0"))

    def test_entity_scoping(self):
        self.post(self.today, "100", "600", Decimal("1500"))
        self.assertEqual(Decimal(self.data("cash_position", entity=self.entity.id)["value"]), Decimal("1500"))
        self.assertEqual(Decimal(self.data("cash_position", entity=self.other_entity.id)["value"]), Decimal("0"))


class ReceivablesPayablesWidgetTests(WidgetTestBase):
    def setUp(self):
        super().setUp()
        self.entity = Entity.objects.create(name="A", code="A")
        self.customer = Party.objects.create(entity=self.entity, name="Acme", party_type=Party.CUSTOMER)
        self.vendor = Party.objects.create(entity=self.entity, name="Vendor", party_type=Party.VENDOR)

    def invoice(self, amount, due_in_days, status=Invoice.SENT):
        invoice = Invoice.objects.create(
            party=self.customer, issue_date=self.today, due_date=self.today + datetime.timedelta(days=due_in_days), status=status
        )
        InvoiceLine.objects.create(invoice=invoice, description="x", quantity=1, unit_price=amount)
        return invoice

    def bill(self, amount, due_in_days, status=Bill.SENT):
        bill = Bill.objects.create(
            party=self.vendor, issue_date=self.today, due_date=self.today + datetime.timedelta(days=due_in_days), status=status
        )
        BillLine.objects.create(bill=bill, description="x", quantity=1, unit_price=amount)
        return bill

    def test_ar_outstanding_nets_payments_and_ignores_drafts(self):
        paid_part = self.invoice(Decimal("1000"), due_in_days=-10)
        Payment.objects.create(invoice=paid_part, amount=Decimal("400"), date=self.today)
        self.invoice(Decimal("200"), due_in_days=10)
        self.invoice(Decimal("5000"), due_in_days=10, status=Invoice.DRAFT)

        payload = self.data("ar_outstanding")
        self.assertEqual(Decimal(payload["value"]), Decimal("800"))
        secondary = {s["key"]: s["value"] for s in payload["secondary"]}
        self.assertEqual(Decimal(secondary["overdue"]), Decimal("600"))
        self.assertEqual(secondary["open_documents"], "2")

    def test_aging_chart_buckets(self):
        self.invoice(Decimal("100"), due_in_days=5)
        self.invoice(Decimal("200"), due_in_days=-45)
        points = {p["label"]: Decimal(p["value"]) for p in self.data("ar_aging")["series"][0]["points"]}
        self.assertEqual(points, {"current": 100, "d1_30": 0, "d31_60": 200, "d61_90": 0, "d90_plus": 0})

    def test_cash_forecast_buckets_by_due_week_with_overdue_first(self):
        self.invoice(Decimal("100"), due_in_days=-3)
        self.invoice(Decimal("200"), due_in_days=0)
        self.invoice(Decimal("300"), due_in_days=8)
        self.invoice(Decimal("999"), due_in_days=40)  # beyond the four-week window
        self.bill(Decimal("50"), due_in_days=27)

        inflow, outflow = self.data("cash_forecast")["series"]
        self.assertEqual(inflow["points"][0]["label"], "overdue")
        self.assertEqual([Decimal(p["value"]) for p in inflow["points"]], [100, 200, 300, 0, 0])
        self.assertEqual([Decimal(p["value"]) for p in outflow["points"]], [0, 0, 0, 0, 50])

    def test_overdue_invoices_table_lists_only_overdue_largest_first(self):
        self.invoice(Decimal("100"), due_in_days=-3)
        self.invoice(Decimal("900"), due_in_days=-1)
        self.invoice(Decimal("5000"), due_in_days=3)
        payload = self.data("overdue_invoices")
        self.assertEqual([Decimal(r["balance_due"]) for r in payload["rows"]], [900, 100])
        self.assertEqual(payload["total_count"], 2)

    def test_upcoming_bills_covers_overdue_and_the_next_two_weeks(self):
        self.bill(Decimal("100"), due_in_days=-2)
        self.bill(Decimal("200"), due_in_days=14)
        self.bill(Decimal("300"), due_in_days=15)
        rows = self.data("upcoming_bills")["rows"]
        self.assertEqual([(Decimal(r["balance_due"]), r["status"]) for r in rows], [(100, "overdue"), (200, "due_soon")])

    def test_attention_lists_only_what_needs_attention_most_severe_first(self):
        self.assertEqual(self.data("attention")["items"], [])

        self.bill(Decimal("200"), due_in_days=3)
        self.invoice(Decimal("100"), due_in_days=-3)
        items = self.data("attention")["items"]
        self.assertEqual([i["key"] for i in items], ["overdue_invoices", "bills_due_soon"])
        self.assertEqual((items[0]["count"], Decimal(items[0]["amount"]), items[0]["severity"]), (1, Decimal("100"), "critical"))

    def test_attention_skips_removed_plugins(self):
        self.invoice(Decimal("100"), due_in_days=-3)
        PluginState.objects.create(key="receivables_payables", is_enabled=False)
        self.assertEqual(self.data("attention")["items"], [])


class InventoryWidgetTests(WidgetTestBase):
    def test_low_stock_lists_pairs_at_or_under_the_threshold(self):
        warehouse = Warehouse.objects.create(code="W1", name="Main")
        low = Item.objects.create(sku="LOW", name="Low")
        plenty = Item.objects.create(sku="OK", name="Plenty")
        StockMove.objects.create(item=low, warehouse=warehouse, move_type=StockMove.RECEIPT, quantity=Decimal("10"))
        StockMove.objects.create(item=low, warehouse=warehouse, move_type=StockMove.PICK, quantity=Decimal("-7"))
        StockMove.objects.create(item=plenty, warehouse=warehouse, move_type=StockMove.RECEIPT, quantity=Decimal("50"))

        payload = self.data("low_stock")
        self.assertEqual([(r["sku"], Decimal(r["quantity"])) for r in payload["rows"]], [("LOW", Decimal("3"))])
        summary = self.data("stock_summary")
        self.assertEqual(summary["value"], "2")
        self.assertEqual(Decimal(summary["secondary"][0]["value"]), Decimal("53"))
