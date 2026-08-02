"""Correctness tests for Core's AI metrics (apps/core/ai_tools.py). These
call the metric functions directly, not through the LLM -- what matters here
is that the *numbers* are right, since a wrong figure narrated confidently
by the AI is a much worse failure than a wrong figure in a report a human
already knows to double-check."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django_tenants.test.cases import TenantTestCase

from apps.core.ai_tools import _journal_entry_preview, cash_position, create_journal_entry, overdue_ap_balance, overdue_ar_balance
from apps.core.models import Account, Bill, BillLine, Entity, Invoice, InvoiceLine, JournalEntry, JournalLine, Party, User


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


class CreateJournalEntryActionTests(TenantTestCase):
    """create_journal_entry (technical.md §8.4) is a thin wrapper around
    JournalEntrySerializer -- these tests exist to confirm that wiring
    actually holds (draft-only, balance validation, entity-scoping), not to
    re-test the serializer's own validation logic from scratch."""

    def setUp(self):
        self.user = User.objects.create_user(username="asker", password="x")
        self.entity = Entity.objects.create(name="Acme A.Ş.", code="ACME")
        self.other_entity = Entity.objects.create(name="Other Co.", code="OTHER")
        self.cash = Account.objects.create(code="100", name="Kasa", account_type=Account.ASSET, entity=self.entity)
        self.capital = Account.objects.create(code="500", name="Sermaye", account_type=Account.EQUITY, entity=self.entity)
        self.other_account = Account.objects.create(
            code="100", name="Kasa", account_type=Account.ASSET, entity=self.other_entity
        )

    def test_creates_a_draft_entry_that_balances(self):
        outcome = create_journal_entry(
            self.user,
            entity=self.entity.id,
            date="2026-08-01",
            memo="Sermaye girişi",
            lines=[
                {"account_id": self.cash.id, "debit": "1000.00", "credit": "0"},
                {"account_id": self.capital.id, "debit": "0", "credit": "1000.00"},
            ],
        )
        entry = JournalEntry.objects.get(id=outcome["result"]["id"])
        self.assertEqual(entry.status, JournalEntry.DRAFT)
        self.assertEqual(entry.lines.count(), 2)
        self.assertEqual(outcome["result"]["status"], JournalEntry.DRAFT)

    def test_unbalanced_lines_raise_instead_of_creating_anything(self):
        with self.assertRaises(ValueError):
            create_journal_entry(
                self.user,
                entity=self.entity.id,
                date="2026-08-01",
                lines=[
                    {"account_id": self.cash.id, "debit": "1000.00", "credit": "0"},
                    {"account_id": self.capital.id, "debit": "0", "credit": "500.00"},
                ],
            )
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_account_from_a_different_entity_raises(self):
        with self.assertRaises(ValueError):
            create_journal_entry(
                self.user,
                entity=self.entity.id,
                date="2026-08-01",
                lines=[
                    {"account_id": self.other_account.id, "debit": "1000.00", "credit": "0"},
                    {"account_id": self.capital.id, "debit": "0", "credit": "1000.00"},
                ],
            )
        self.assertEqual(JournalEntry.objects.count(), 0)


class JournalEntryPreviewTests(TenantTestCase):
    def setUp(self):
        self.entity = Entity.objects.create(name="Acme A.Ş.", code="ACME")
        self.cash = Account.objects.create(code="100", name="Kasa", account_type=Account.ASSET, entity=self.entity)

    def test_preview_includes_account_code_and_name(self):
        preview = _journal_entry_preview(
            entity=self.entity.id,
            date="2026-08-01",
            memo="test",
            lines=[{"account_id": self.cash.id, "debit": "100.00", "credit": "0"}],
        )
        self.assertIn("100 — Kasa", preview)

    def test_preview_falls_back_gracefully_for_unknown_account(self):
        preview = _journal_entry_preview(
            entity=self.entity.id, date="2026-08-01", lines=[{"account_id": 999999, "debit": "100.00", "credit": "0"}]
        )
        self.assertIn("hesap #999999", preview)
