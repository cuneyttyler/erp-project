"""Correctness tests for Core's AI metrics (apps/core/ai_tools.py). These
call the metric functions directly, not through the LLM -- what matters here
is that the *numbers* are right, since a wrong figure narrated confidently
by the AI is a much worse failure than a wrong figure in a report a human
already knows to double-check."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django_tenants.test.cases import TenantTestCase

from apps.core.ai_tools import (
    cash_position,
    flagged_vendor_bills,
    monthly_revenue,
    overdue_ap_balance,
    overdue_ar_balance,
    revenue_by_customer,
    spend_by_vendor,
)
from apps.core.models import Account, Bill, BillLine, Entity, Invoice, InvoiceLine, JournalEntry, JournalLine, Party


class CashPositionTests(TenantTestCase):
    def setUp(self):
        self.kasa = Account.objects.create(code="100", name="Kasa", account_type=Account.ASSET)
        self.bank = Account.objects.create(code="102", name="Bankalar", account_type=Account.ASSET)
        self.capital = Account.objects.create(code="500", name="Sermaye", account_type=Account.EQUITY)

    def _post_entry(self, debit_account, credit_account, amount):
        entry = JournalEntry.objects.create(date=timezone.localdate(), status=JournalEntry.DRAFT)
        JournalLine.objects.create(journal_entry=entry, account=debit_account, debit=amount, credit=0)
        JournalLine.objects.create(journal_entry=entry, account=credit_account, debit=0, credit=amount)
        entry.post()

    def test_sums_only_cash_and_bank_accounts(self):
        self._post_entry(self.kasa, self.capital, Decimal("1000.00"))
        self._post_entry(self.bank, self.capital, Decimal("5000.00"))
        outcome = cash_position()
        self.assertEqual(outcome["result"]["cash_and_bank_balance"], "6000.00")

    def test_ignores_unposted_draft_entries(self):
        entry = JournalEntry.objects.create(date=timezone.localdate(), status=JournalEntry.DRAFT)
        JournalLine.objects.create(journal_entry=entry, account=self.kasa, debit=Decimal("9999.00"), credit=0)
        JournalLine.objects.create(journal_entry=entry, account=self.capital, debit=0, credit=Decimal("9999.00"))
        outcome = cash_position()
        self.assertEqual(outcome["result"]["cash_and_bank_balance"], "0")

    def test_returns_a_citation(self):
        outcome = cash_position()
        self.assertEqual(outcome["citations"][0]["route"], "/trial-balance")


class OverdueBalanceTests(TenantTestCase):
    def setUp(self):
        self.customer = Party.objects.create(name="Acme A.Ş.", party_type=Party.CUSTOMER)
        self.vendor = Party.objects.create(name="Tedarikçi Ltd.", party_type=Party.VENDOR)

    def test_overdue_ar_balance_only_counts_past_due_sent_invoices(self):
        today = timezone.localdate()
        overdue_invoice = Invoice.objects.create(
            party=self.customer, issue_date=today - timedelta(days=40), due_date=today - timedelta(days=10)
        )
        InvoiceLine.objects.create(invoice=overdue_invoice, description="x", quantity=1, unit_price=Decimal("1500.00"))
        overdue_invoice.mark_sent()

        not_yet_due_invoice = Invoice.objects.create(
            party=self.customer, issue_date=today, due_date=today + timedelta(days=30)
        )
        InvoiceLine.objects.create(invoice=not_yet_due_invoice, description="x", quantity=1, unit_price=Decimal("500.00"))
        not_yet_due_invoice.mark_sent()

        outcome = overdue_ar_balance()
        self.assertEqual(outcome["result"]["total_overdue"], "1500.00")
        self.assertEqual(outcome["result"]["count"], 1)
        self.assertEqual(outcome["result"]["top_customers"][0]["party"], "Acme A.Ş.")

    def test_overdue_ap_balance_only_counts_past_due_sent_bills(self):
        today = timezone.localdate()
        overdue_bill = Bill.objects.create(
            party=self.vendor, issue_date=today - timedelta(days=50), due_date=today - timedelta(days=20)
        )
        BillLine.objects.create(bill=overdue_bill, description="x", quantity=1, unit_price=Decimal("800.00"))
        overdue_bill.mark_sent()

        outcome = overdue_ap_balance()
        self.assertEqual(outcome["result"]["total_overdue"], "800.00")
        self.assertEqual(outcome["result"]["top_vendors"][0]["party"], "Tedarikçi Ltd.")

    def test_no_overdue_documents_returns_zero(self):
        outcome = overdue_ar_balance()
        self.assertEqual(outcome["result"]["total_overdue"], "0.00")
        self.assertEqual(outcome["result"]["count"], 0)


class MonthlyRevenueSeriesTests(TenantTestCase):
    """REQ-BI-001/002."""

    def setUp(self):
        self.entity = Entity.objects.create(name="Acme A.Ş.", code="ACME")
        self.cash = Account.objects.create(code="100", name="Kasa", account_type=Account.ASSET, entity=self.entity)
        self.revenue = Account.objects.create(code="600", name="Yurtiçi Satışlar", account_type=Account.REVENUE, entity=self.entity)
        self.returns = Account.objects.create(code="610", name="Satıştan İadeler", account_type=Account.REVENUE, entity=self.entity)

    def _post(self, date, revenue_account, amount, debit_account=None):
        entry = JournalEntry.objects.create(entity=self.entity, date=date, status=JournalEntry.DRAFT)
        JournalLine.objects.create(journal_entry=entry, account=debit_account or self.cash, debit=amount, credit=0)
        JournalLine.objects.create(journal_entry=entry, account=revenue_account, debit=0, credit=amount)
        entry.post()

    def test_returns_the_right_number_of_month_buckets_in_order(self):
        outcome = monthly_revenue(months=3)
        self.assertEqual(len(outcome["result"]["series"]), 3)
        labels = [p["label"] for p in outcome["result"]["series"]]
        self.assertEqual(labels, sorted(labels))

    def test_sums_revenue_into_the_correct_month_bucket(self):
        today = timezone.localdate()
        self._post(today, self.revenue, Decimal("500.00"))
        outcome = monthly_revenue(months=1)
        self.assertEqual(outcome["result"]["series"][0]["value"], "500.00")

    def test_a_contra_revenue_debit_reduces_the_bucket(self):
        today = timezone.localdate()
        self._post(today, self.revenue, Decimal("500.00"))
        # A return posts a debit to a Revenue-type account (610) -- net
        # revenue for the month should drop accordingly.
        entry = JournalEntry.objects.create(entity=self.entity, date=today, status=JournalEntry.DRAFT)
        JournalLine.objects.create(journal_entry=entry, account=self.returns, debit=Decimal("100.00"), credit=0)
        JournalLine.objects.create(journal_entry=entry, account=self.cash, debit=0, credit=Decimal("100.00"))
        entry.post()

        outcome = monthly_revenue(months=1)
        self.assertEqual(outcome["result"]["series"][0]["value"], "400.00")

    def test_unposted_entries_are_excluded(self):
        today = timezone.localdate()
        entry = JournalEntry.objects.create(entity=self.entity, date=today, status=JournalEntry.DRAFT)
        JournalLine.objects.create(journal_entry=entry, account=self.cash, debit=Decimal("999.00"), credit=0)
        JournalLine.objects.create(journal_entry=entry, account=self.revenue, debit=0, credit=Decimal("999.00"))
        # deliberately not posted
        outcome = monthly_revenue(months=1)
        self.assertEqual(outcome["result"]["series"][0]["value"], "0.00")


class RevenueByCustomerSeriesTests(TenantTestCase):
    def setUp(self):
        self.acme = Party.objects.create(name="Acme A.Ş.", party_type=Party.CUSTOMER)
        self.other = Party.objects.create(name="Diğer A.Ş.", party_type=Party.CUSTOMER)

    def _sent_invoice(self, party, amount):
        today = timezone.localdate()
        invoice = Invoice.objects.create(party=party, issue_date=today, due_date=today + timedelta(days=30))
        InvoiceLine.objects.create(invoice=invoice, description="x", quantity=1, unit_price=amount)
        invoice.mark_sent()

    def test_ranks_customers_by_total_descending(self):
        self._sent_invoice(self.acme, Decimal("100.00"))
        self._sent_invoice(self.other, Decimal("500.00"))
        outcome = revenue_by_customer(top_n=10)
        labels = [p["label"] for p in outcome["result"]["series"]]
        self.assertEqual(labels[0], "Diğer A.Ş.")

    def test_respects_top_n(self):
        self._sent_invoice(self.acme, Decimal("100.00"))
        self._sent_invoice(self.other, Decimal("500.00"))
        outcome = revenue_by_customer(top_n=1)
        self.assertEqual(len(outcome["result"]["series"]), 1)

    def test_draft_invoices_are_excluded(self):
        Invoice.objects.create(party=self.acme, issue_date=timezone.localdate(), due_date=timezone.localdate())
        outcome = revenue_by_customer()
        self.assertEqual(outcome["result"]["series"], [])


class SpendByVendorSeriesTests(TenantTestCase):
    def test_ranks_vendors_by_total_descending(self):
        vendor_a = Party.objects.create(name="Tedarikçi A", party_type=Party.VENDOR)
        vendor_b = Party.objects.create(name="Tedarikçi B", party_type=Party.VENDOR)
        today = timezone.localdate()

        bill_a = Bill.objects.create(party=vendor_a, issue_date=today, due_date=today + timedelta(days=30))
        BillLine.objects.create(bill=bill_a, description="x", quantity=1, unit_price=Decimal("200.00"))
        bill_a.mark_sent()

        bill_b = Bill.objects.create(party=vendor_b, issue_date=today, due_date=today + timedelta(days=30))
        BillLine.objects.create(bill=bill_b, description="x", quantity=1, unit_price=Decimal("900.00"))
        bill_b.mark_sent()

        outcome = spend_by_vendor(top_n=10)
        self.assertEqual(outcome["result"]["series"][0]["label"], "Tedarikçi B")


class BillAnomalyWarningTests(TenantTestCase):
    """REQ-BI-004."""

    def setUp(self):
        self.vendor = Party.objects.create(name="Tedarikçi A", party_type=Party.VENDOR)

    def _sent_bill(self, amount):
        today = timezone.localdate()
        bill = Bill.objects.create(party=self.vendor, issue_date=today, due_date=today + timedelta(days=30))
        BillLine.objects.create(bill=bill, description="x", quantity=1, unit_price=amount)
        bill.mark_sent()
        return bill

    def test_no_warning_with_insufficient_history(self):
        self._sent_bill(Decimal("100.00"))
        new_bill = self._sent_bill(Decimal("1000.00"))
        self.assertIsNone(new_bill.anomaly_warning)

    def test_flags_a_bill_well_above_the_trailing_average(self):
        self._sent_bill(Decimal("100.00"))
        self._sent_bill(Decimal("100.00"))
        new_bill = self._sent_bill(Decimal("500.00"))
        self.assertIsNotNone(new_bill.anomaly_warning)
        self.assertIn("Tedarikçi A", new_bill.anomaly_warning)

    def test_does_not_flag_a_bill_close_to_the_average(self):
        self._sent_bill(Decimal("100.00"))
        self._sent_bill(Decimal("100.00"))
        new_bill = self._sent_bill(Decimal("110.00"))
        self.assertIsNone(new_bill.anomaly_warning)

    def test_flagged_vendor_bills_metric_lists_only_anomalous_ones(self):
        self._sent_bill(Decimal("100.00"))
        self._sent_bill(Decimal("100.00"))
        self._sent_bill(Decimal("500.00"))
        outcome = flagged_vendor_bills()
        self.assertEqual(outcome["result"]["count"], 1)
        self.assertEqual(outcome["result"]["bills"][0]["total"], "500.00")
