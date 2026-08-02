"""Correctness tests for POS checkout/return orchestration and the Z-report
(REQ-POS-001/002/004/005). What matters here: stock actually moves, the GL
entry actually balances and posts, and the cash reconciliation numbers are
right -- a wrong Z-report total is a much worse failure than a UI glitch."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django_tenants.test.cases import TenantTestCase

from apps.core.models import Account, Entity, Item, JournalEntry, User
from apps.inventory import services as inventory_services
from apps.inventory.models import Warehouse
from apps.pos import services
from apps.pos.models import POSPayment, POSSale, POSShift, Store, Till


class POSTestBase(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cashier", password="x")
        self.entity = Entity.objects.create(name="Acme Perakende", code="ACME")
        self.warehouse = Warehouse.objects.create(code="MAG1", name="Mağaza 1 Depo")
        self.store = Store.objects.create(entity=self.entity, warehouse=self.warehouse, code="S1", name="Kadıköy Mağaza")
        self.till = Till.objects.create(store=self.store, code="T1", name="Kasa 1")
        self.shift = POSShift.objects.create(till=self.till, opened_by=self.user, opening_cash=Decimal("500.00"))

        self.cash = Account.objects.create(code="100", name="Kasa", account_type=Account.ASSET, entity=self.entity)
        self.card = Account.objects.create(code="102", name="Bankalar", account_type=Account.ASSET, entity=self.entity)
        self.revenue = Account.objects.create(code="600", name="Yurtiçi Satışlar", account_type=Account.REVENUE, entity=self.entity)
        self.returns_acct = Account.objects.create(code="610", name="Satıştan İadeler (-)", account_type=Account.REVENUE, entity=self.entity)

        self.item = Item.objects.create(sku="SKU-1", name="Widget")
        inventory_services.record_receipt(item=self.item, warehouse=self.warehouse, quantity=Decimal("100"), reference="seed")

    def _checkout(self, quantity="2", unit_price="50.00", method=POSPayment.CASH, **kwargs):
        amount = Decimal(quantity) * Decimal(unit_price)
        return services.checkout(
            self.shift,
            lines=[{"item_id": self.item.id, "quantity": quantity, "unit_price": unit_price}],
            payments=[{"method": method, "amount": str(amount)}],
            user=self.user,
            **kwargs,
        )


class CheckoutTests(POSTestBase):
    def test_checkout_creates_sale_with_correct_subtotal(self):
        sale = self._checkout(quantity="2", unit_price="50.00")
        self.assertEqual(sale.subtotal, Decimal("100.00"))
        self.assertEqual(sale.status, POSSale.COMPLETED)

    def test_checkout_deducts_stock(self):
        self._checkout(quantity="3", unit_price="50.00")
        remaining = inventory_services.get_quantity_on_hand(self.item, self.warehouse)
        self.assertEqual(remaining, Decimal("97"))

    def test_checkout_posts_a_balanced_journal_entry(self):
        sale = self._checkout(quantity="2", unit_price="50.00", method=POSPayment.CARD)
        entry = sale.journal_entry
        self.assertEqual(entry.status, JournalEntry.POSTED)
        total_debit = sum(l.debit for l in entry.lines.all())
        total_credit = sum(l.credit for l in entry.lines.all())
        self.assertEqual(total_debit, total_credit)
        self.assertEqual(total_debit, Decimal("100.00"))
        card_line = entry.lines.get(account=self.card)
        self.assertEqual(card_line.debit, Decimal("100.00"))
        revenue_line = entry.lines.get(account=self.revenue)
        self.assertEqual(revenue_line.credit, Decimal("100.00"))

    def test_checkout_applies_line_discount(self):
        sale = services.checkout(
            self.shift,
            lines=[{"item_id": self.item.id, "quantity": "1", "unit_price": "50.00", "discount_amount": "10.00"}],
            payments=[{"method": POSPayment.CASH, "amount": "40.00"}],
            user=self.user,
        )
        self.assertEqual(sale.subtotal, Decimal("40.00"))

    def test_checkout_rejects_insufficient_stock(self):
        with self.assertRaises(ValidationError):
            self._checkout(quantity="1000", unit_price="50.00")
        self.assertEqual(POSSale.objects.count(), 0)

    def test_checkout_rejects_payments_not_matching_subtotal(self):
        with self.assertRaises(ValidationError):
            services.checkout(
                self.shift,
                lines=[{"item_id": self.item.id, "quantity": "2", "unit_price": "50.00"}],
                payments=[{"method": POSPayment.CASH, "amount": "50.00"}],
                user=self.user,
            )
        self.assertEqual(POSSale.objects.count(), 0)

    def test_checkout_rejects_a_sale_on_a_closed_shift(self):
        self.shift.close(Decimal("500.00"))
        with self.assertRaises(ValidationError):
            self._checkout()

    def test_checkout_is_idempotent_on_client_reference(self):
        first = self._checkout(quantity="1", unit_price="50.00", client_reference="offline-abc123")
        second = services.checkout(
            self.shift,
            lines=[{"item_id": self.item.id, "quantity": "1", "unit_price": "50.00"}],
            payments=[{"method": POSPayment.CASH, "amount": "50.00"}],
            user=self.user,
            client_reference="offline-abc123",
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(POSSale.objects.count(), 1)
        remaining = inventory_services.get_quantity_on_hand(self.item, self.warehouse)
        self.assertEqual(remaining, Decimal("99"))

    def test_split_payment_across_two_methods(self):
        sale = services.checkout(
            self.shift,
            lines=[{"item_id": self.item.id, "quantity": "2", "unit_price": "50.00"}],
            payments=[{"method": POSPayment.CASH, "amount": "60.00"}, {"method": POSPayment.CARD, "amount": "40.00"}],
            user=self.user,
        )
        self.assertEqual(sale.total_paid, Decimal("100.00"))
        entry = sale.journal_entry
        self.assertEqual(entry.lines.get(account=self.cash).debit, Decimal("60.00"))
        self.assertEqual(entry.lines.get(account=self.card).debit, Decimal("40.00"))


class ReturnSaleTests(POSTestBase):
    def setUp(self):
        super().setUp()
        self.sale = self._checkout(quantity="4", unit_price="50.00")

    def test_full_return_restores_stock_and_marks_returned(self):
        line = self.sale.lines.get()
        services.return_sale(
            self.sale, lines=[{"sale_line_id": line.id, "quantity": "4"}], user=self.user, refund_method=POSPayment.CASH
        )
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.status, POSSale.RETURNED)
        remaining = inventory_services.get_quantity_on_hand(self.item, self.warehouse)
        self.assertEqual(remaining, Decimal("100"))

    def test_partial_return_marks_partially_returned(self):
        line = self.sale.lines.get()
        services.return_sale(
            self.sale, lines=[{"sale_line_id": line.id, "quantity": "1"}], user=self.user, refund_method=POSPayment.CASH
        )
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.status, POSSale.PARTIALLY_RETURNED)

    def test_return_posts_a_balanced_reversing_journal_entry(self):
        line = self.sale.lines.get()
        pos_return = services.return_sale(
            self.sale, lines=[{"sale_line_id": line.id, "quantity": "2"}], user=self.user, refund_method=POSPayment.CASH
        )
        entry = pos_return.journal_entry
        self.assertEqual(entry.status, JournalEntry.POSTED)
        self.assertEqual(entry.lines.get(account=self.returns_acct).debit, Decimal("100.00"))
        self.assertEqual(entry.lines.get(account=self.cash).credit, Decimal("100.00"))

    def test_returning_more_than_remaining_raises(self):
        line = self.sale.lines.get()
        with self.assertRaises(ValidationError):
            services.return_sale(
                self.sale, lines=[{"sale_line_id": line.id, "quantity": "5"}], user=self.user, refund_method=POSPayment.CASH
            )

    def test_returning_twice_the_full_quantity_raises_on_the_second_call(self):
        line = self.sale.lines.get()
        services.return_sale(
            self.sale, lines=[{"sale_line_id": line.id, "quantity": "4"}], user=self.user, refund_method=POSPayment.CASH
        )
        with self.assertRaises(ValidationError):
            services.return_sale(
                self.sale, lines=[{"sale_line_id": line.id, "quantity": "1"}], user=self.user, refund_method=POSPayment.CASH
            )

    def test_discounted_line_refunds_the_net_price_proportionally(self):
        sale = services.checkout(
            self.shift,
            lines=[{"item_id": self.item.id, "quantity": "2", "unit_price": "50.00", "discount_amount": "20.00"}],
            payments=[{"method": POSPayment.CASH, "amount": "80.00"}],
            user=self.user,
        )
        line = sale.lines.get()
        pos_return = services.return_sale(
            sale, lines=[{"sale_line_id": line.id, "quantity": "1"}], user=self.user, refund_method=POSPayment.CASH
        )
        # net_unit_price = (2*50 - 20) / 2 = 40 -- refunding 1 unit should be 40.00, not 50.00
        self.assertEqual(pos_return.lines.get().refund_amount, Decimal("40.00"))


class ShiftCloseAndZReportTests(POSTestBase):
    def test_close_sets_status_and_counted_cash(self):
        self.shift.close(Decimal("620.00"))
        self.shift.refresh_from_db()
        self.assertEqual(self.shift.status, POSShift.CLOSED)
        self.assertEqual(self.shift.closing_cash_counted, Decimal("620.00"))

    def test_closing_twice_raises(self):
        self.shift.close(Decimal("620.00"))
        with self.assertRaises(ValidationError):
            self.shift.close(Decimal("620.00"))

    def test_z_report_matches_cash_sale_with_no_discrepancy(self):
        self._checkout(quantity="2", unit_price="50.00", method=POSPayment.CASH)
        self.shift.close(Decimal("600.00"))  # opening 500 + 100 cash sale
        report = self.shift.z_report()
        self.assertEqual(report["transaction_count"], 1)
        self.assertEqual(report["gross_sales"], "100.00")
        self.assertEqual(report["net_sales"], "100.00")
        self.assertEqual(report["expected_cash"], "600.00")
        self.assertEqual(report["cash_discrepancy"], "0.00")

    def test_z_report_flags_a_cash_discrepancy(self):
        self._checkout(quantity="2", unit_price="50.00", method=POSPayment.CASH)
        self.shift.close(Decimal("590.00"))  # 10 short
        report = self.shift.z_report()
        self.assertEqual(report["cash_discrepancy"], "-10.00")

    def test_z_report_nets_out_a_return(self):
        sale = self._checkout(quantity="2", unit_price="50.00", method=POSPayment.CASH)
        line = sale.lines.get()
        services.return_sale(sale, lines=[{"sale_line_id": line.id, "quantity": "1"}], user=self.user, refund_method=POSPayment.CASH)
        report = self.shift.z_report()
        self.assertEqual(report["gross_sales"], "100.00")
        self.assertEqual(report["returns_total"], "50.00")
        self.assertEqual(report["net_sales"], "50.00")
        self.assertEqual(report["expected_cash"], "550.00")  # 500 opening + 100 sale - 50 refund

    def test_z_report_before_closing_has_no_discrepancy_field(self):
        self._checkout(quantity="1", unit_price="50.00")
        report = self.shift.z_report()
        self.assertIsNone(report["closing_cash_counted"])
        self.assertIsNone(report["cash_discrepancy"])
