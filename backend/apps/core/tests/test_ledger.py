"""
General Ledger / Chart of Accounts tests (REQ-CORE-GL-001/002/008).

Uses TenantTestCase so these run inside a real, throwaway tenant schema --
exercising the exact schema-per-tenant isolation path the app relies on in
production, not a shortcut around it.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import Account, JournalEntry, JournalLine, User


class JournalEntryBalanceTests(TenantTestCase):
    def setUp(self):
        self.cash = Account.objects.create(code="100", name="Kasa", account_type=Account.ASSET)
        self.sales = Account.objects.create(code="600", name="Yurtiçi Satışlar", account_type=Account.REVENUE)

    def _make_entry(self, debit, credit):
        entry = JournalEntry.objects.create(date="2026-01-01", memo="test entry")
        JournalLine.objects.create(journal_entry=entry, account=self.cash, debit=debit, credit=0)
        JournalLine.objects.create(journal_entry=entry, account=self.sales, debit=0, credit=credit)
        return entry

    def test_balanced_entry_posts_successfully(self):
        entry = self._make_entry(Decimal("100.00"), Decimal("100.00"))
        entry.post()
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.POSTED)
        self.assertIsNotNone(entry.posted_at)

    def test_unbalanced_entry_cannot_be_posted(self):
        entry = self._make_entry(Decimal("100.00"), Decimal("90.00"))
        with self.assertRaises(ValidationError):
            entry.post()
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.DRAFT)

    def test_entry_with_no_lines_cannot_be_posted(self):
        entry = JournalEntry.objects.create(date="2026-01-01", memo="empty")
        with self.assertRaises(ValidationError):
            entry.post()

    def test_posted_entry_survives_as_immutable_record(self):
        # REQ-CORE-GL-008: no application code path un-posts an entry.
        entry = self._make_entry(Decimal("50.00"), Decimal("50.00"))
        entry.post()
        self.assertFalse(hasattr(entry, "unpost"))


class TrialBalanceQueryTests(TenantTestCase):
    def setUp(self):
        self.cash = Account.objects.create(code="100", name="Kasa", account_type=Account.ASSET)
        self.sales = Account.objects.create(code="600", name="Yurtiçi Satışlar", account_type=Account.REVENUE)

    def test_only_posted_entries_count_toward_balances(self):
        draft = JournalEntry.objects.create(date="2026-01-01", memo="draft, should not count")
        JournalLine.objects.create(journal_entry=draft, account=self.cash, debit=Decimal("500.00"), credit=0)
        JournalLine.objects.create(journal_entry=draft, account=self.sales, debit=0, credit=Decimal("500.00"))

        posted = JournalEntry.objects.create(date="2026-01-02", memo="posted")
        JournalLine.objects.create(journal_entry=posted, account=self.cash, debit=Decimal("100.00"), credit=0)
        JournalLine.objects.create(journal_entry=posted, account=self.sales, debit=0, credit=Decimal("100.00"))
        posted.post()

        posted_debit_total = sum(
            line.debit
            for line in JournalLine.objects.filter(
                account=self.cash, journal_entry__status=JournalEntry.POSTED
            )
        )
        self.assertEqual(posted_debit_total, Decimal("100.00"))


class TrialBalanceAPITests(TenantTestCase):
    """
    Regression coverage for the raw-dict-Response bug: TrialBalanceView used
    to hand Decimal aggregates straight to Response(), which DRF's JSON
    encoder silently downgrades to float outside of a serializer field. A
    financial total must never round-trip through JSON as a float.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="x")
        self.cash = Account.objects.create(code="100", name="Kasa", account_type=Account.ASSET)
        self.sales = Account.objects.create(code="600", name="Yurtiçi Satışlar", account_type=Account.REVENUE)
        entry = JournalEntry.objects.create(date="2026-01-01", memo="test")
        JournalLine.objects.create(journal_entry=entry, account=self.cash, debit=Decimal("100.00"), credit=0)
        JournalLine.objects.create(journal_entry=entry, account=self.sales, debit=0, credit=Decimal("100.00"))
        entry.post()

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_totals_are_serialized_as_precise_strings_not_floats(self):
        # TenantTestCase resolves tenants by hostname (TenantMainMiddleware),
        # using 'tenant.test.com' for its throwaway test tenant -- without
        # this HTTP_HOST the request 404s before ever reaching our view.
        response = self.client.get(
            "/api/v1/core/reports/trial-balance/", HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(response.status_code, 200)
        # The raw response body must contain a quoted string ("100.00"),
        # not a bare JSON number (100.0) -- assert on the bytes, not just
        # response.data, since Python would silently accept either as equal
        # to Decimal("100.00") and mask exactly this regression.
        self.assertIn(b'"100.00"', response.content)
        # DRF's DecimalField.to_representation coerces to a string by design
        # (that's the fix) -- response.data holds '100.00' as str, not Decimal.
        cash_row = next(row for row in response.data if row["code"] == "100")
        self.assertEqual(cash_row["total_debit"], "100.00")
        self.assertIsInstance(cash_row["total_debit"], str)
