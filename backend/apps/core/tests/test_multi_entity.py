"""Multi-entity consolidation tests (REQ-CORE-ENT-001/002)."""

from decimal import Decimal

from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import Account, Entity, Invoice, InvoiceLine, JournalEntry, JournalLine, Party, User


class EntityScopedListEndpointsDontErrorTests(TenantTestCase):
    """
    Regression coverage for a real bug: Account/JournalEntry/Party's
    `entity` field is null=True at the DB level (migration-backfill
    reasons, see models.py), and declaring it required via
    Meta.extra_kwargs alone collided with a `default=None` DRF's own
    ModelSerializer auto-generation adds for any null=True FK -- "may not
    set both `required` and `default`", a 500 on every single list/create
    call. Caught via a live Playwright run hitting `GET /accounts/
    ?entity=<id>` through the actual frontend, not by the API test suite
    (every other test in this file only exercises POST /journal-entries/,
    which happened not to trip the same assertion) -- this test closes
    that gap by explicitly hitting the plain GET list endpoints DRF's own
    field-building code runs for.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="x")
        self.entity = Entity.objects.create(code="MAIN", name="Ana Şirket")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_account_list_with_entity_filter(self):
        response = self.client.get(
            "/api/v1/core/accounts/", {"entity": self.entity.id}, HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_journal_entry_list_with_entity_filter(self):
        response = self.client.get(
            "/api/v1/core/journal-entries/", {"entity": self.entity.id}, HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_party_list_with_entity_filter(self):
        response = self.client.get(
            "/api/v1/core/parties/", {"entity": self.entity.id}, HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(response.status_code, 200, response.content)


def _post_entry(entity, debit_account, credit_account, amount, date="2026-01-01"):
    entry = JournalEntry.objects.create(entity=entity, date=date, memo="test")
    JournalLine.objects.create(journal_entry=entry, account=debit_account, debit=amount, credit=0)
    JournalLine.objects.create(journal_entry=entry, account=credit_account, debit=0, credit=amount)
    entry.post()
    return entry


class AccountEntityScopingTests(TenantTestCase):
    def test_same_code_allowed_across_different_entities(self):
        entity_a = Entity.objects.create(code="A", name="Entity A")
        entity_b = Entity.objects.create(code="B", name="Entity B")
        Account.objects.create(entity=entity_a, code="100", name="Kasa", account_type=Account.ASSET)
        # Must not raise -- same code, different entity, is exactly the point.
        Account.objects.create(entity=entity_b, code="100", name="Kasa", account_type=Account.ASSET)
        self.assertEqual(Account.objects.filter(code="100").count(), 2)


class JournalEntryEntityValidationTests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="x")
        self.entity_a = Entity.objects.create(code="A", name="Entity A")
        self.entity_b = Entity.objects.create(code="B", name="Entity B")
        self.cash_a = Account.objects.create(entity=self.entity_a, code="100", name="Kasa", account_type=Account.ASSET)
        self.sales_a = Account.objects.create(
            entity=self.entity_a, code="600", name="Satışlar", account_type=Account.REVENUE
        )
        self.cash_b = Account.objects.create(entity=self.entity_b, code="100", name="Kasa", account_type=Account.ASSET)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_cannot_create_entry_mixing_accounts_from_different_entities(self):
        response = self.client.post(
            "/api/v1/core/journal-entries/",
            {
                "entity": self.entity_a.id,
                "date": "2026-01-01",
                "memo": "cross-entity",
                "lines": [
                    {"account": self.cash_a.id, "debit": "100.00", "credit": "0"},
                    {"account": self.cash_b.id, "debit": "0", "credit": "100.00"},
                ],
            },
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 400)

    def test_can_create_entry_with_accounts_from_the_same_entity(self):
        response = self.client.post(
            "/api/v1/core/journal-entries/",
            {
                "entity": self.entity_a.id,
                "date": "2026-01-01",
                "memo": "same entity",
                "lines": [
                    {"account": self.cash_a.id, "debit": "100.00", "credit": "0"},
                    {"account": self.sales_a.id, "debit": "0", "credit": "100.00"},
                ],
            },
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 201, response.content)


class TrialBalanceEntityScopingTests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="x")
        self.entity_a = Entity.objects.create(code="A", name="Entity A")
        self.entity_b = Entity.objects.create(code="B", name="Entity B")

        self.cash_a = Account.objects.create(entity=self.entity_a, code="100", name="Kasa", account_type=Account.ASSET)
        self.sales_a = Account.objects.create(
            entity=self.entity_a, code="600", name="Satışlar", account_type=Account.REVENUE
        )
        _post_entry(self.entity_a, self.cash_a, self.sales_a, Decimal("1000.00"))

        self.cash_b = Account.objects.create(entity=self.entity_b, code="100", name="Kasa", account_type=Account.ASSET)
        self.sales_b = Account.objects.create(
            entity=self.entity_b, code="600", name="Satışlar", account_type=Account.REVENUE
        )
        _post_entry(self.entity_b, self.cash_b, self.sales_b, Decimal("500.00"))

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_requires_entity_or_consolidated_param(self):
        response = self.client.get("/api/v1/core/reports/trial-balance/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 400)

    def test_single_entity_view_excludes_other_entities(self):
        response = self.client.get(
            "/api/v1/core/reports/trial-balance/",
            {"entity": self.entity_a.id},
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 200)
        cash_row = next(r for r in response.data if r["code"] == "100")
        self.assertEqual(cash_row["total_debit"], "1000.00")

    def test_consolidated_view_sums_across_entities(self):
        response = self.client.get(
            "/api/v1/core/reports/trial-balance/",
            {"consolidated": "true"},
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 200)
        cash_row = next(r for r in response.data if r["code"] == "100")
        self.assertEqual(cash_row["total_debit"], "1500.00")

    def test_consolidated_view_excludes_intercompany_accounts(self):
        ic_receivable_a = Account.objects.create(
            entity=self.entity_a, code="181", name="Grup İçi Alacaklar", account_type=Account.ASSET,
            is_intercompany=True,
        )
        equity_a = Account.objects.create(
            entity=self.entity_a, code="500", name="Sermaye", account_type=Account.EQUITY
        )
        _post_entry(self.entity_a, ic_receivable_a, equity_a, Decimal("9999.00"))

        response = self.client.get(
            "/api/v1/core/reports/trial-balance/",
            {"consolidated": "true"},
            HTTP_HOST="tenant.test.com",
        )
        codes = [r["code"] for r in response.data]
        self.assertNotIn("181", codes)


class PartyAndAgingEntityScopingTests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="x")
        self.entity_a = Entity.objects.create(code="A", name="Entity A")
        self.entity_b = Entity.objects.create(code="B", name="Entity B")
        self.customer_a = Party.objects.create(entity=self.entity_a, name="Müşteri A", party_type=Party.CUSTOMER)
        self.customer_b = Party.objects.create(entity=self.entity_b, name="Müşteri B", party_type=Party.CUSTOMER)

        invoice_a = Invoice.objects.create(party=self.customer_a, issue_date="2026-01-01", due_date="2026-01-31")
        InvoiceLine.objects.create(invoice=invoice_a, description="x", quantity=1, unit_price=Decimal("100.00"))
        invoice_a.mark_sent()
        self.invoice_a = invoice_a

        invoice_b = Invoice.objects.create(party=self.customer_b, issue_date="2026-01-01", due_date="2026-01-31")
        InvoiceLine.objects.create(invoice=invoice_b, description="y", quantity=1, unit_price=Decimal("200.00"))
        invoice_b.mark_sent()
        self.invoice_b = invoice_b

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_party_list_filters_by_entity(self):
        response = self.client.get(
            "/api/v1/core/parties/", {"entity": self.entity_a.id}, HTTP_HOST="tenant.test.com"
        )
        names = [p["name"] for p in response.data["results"]]
        self.assertIn("Müşteri A", names)
        self.assertNotIn("Müşteri B", names)

    def test_invoice_list_filters_by_entity_via_party(self):
        response = self.client.get(
            "/api/v1/core/invoices/", {"entity": self.entity_a.id}, HTTP_HOST="tenant.test.com"
        )
        ids = [i["id"] for i in response.data["results"]]
        self.assertIn(self.invoice_a.id, ids)
        self.assertNotIn(self.invoice_b.id, ids)

    def test_ar_aging_filters_by_entity(self):
        response = self.client.get(
            "/api/v1/core/reports/ar-aging/", {"entity": self.entity_b.id}, HTTP_HOST="tenant.test.com"
        )
        ids = [row["document_id"] for row in response.data]
        self.assertEqual(ids, [self.invoice_b.id])


class EntityViewSetTests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="x")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_and_list_entities(self):
        response = self.client.post(
            "/api/v1/core/entities/",
            {"name": "Yeni Şirket", "code": "NEW", "currency": "TRY"},
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 201, response.content)

        list_response = self.client.get("/api/v1/core/entities/", HTTP_HOST="tenant.test.com")
        codes = [e["code"] for e in list_response.data["results"]]
        self.assertIn("NEW", codes)
