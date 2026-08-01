"""Correctness tests for Core's AI metrics (apps/core/ai_tools.py). These
call the metric functions directly, not through the LLM -- what matters here
is that the *numbers* are right, since a wrong figure narrated confidently
by the AI is a much worse failure than a wrong figure in a report a human
already knows to double-check."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django_tenants.test.cases import TenantTestCase

from apps.core.ai_tools import cash_position, overdue_ap_balance, overdue_ar_balance
from apps.core.models import Account, Bill, BillLine, Invoice, InvoiceLine, JournalEntry, JournalLine, Party


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
