"""
AR/AP tests (REQ-CORE-AR-001/002/003, REQ-CORE-AP-001/002).
"""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import Bill, BillLine, Invoice, InvoiceLine, Party, Payment, User


class InvoiceLifecycleTests(TenantTestCase):
    def setUp(self):
        self.customer = Party.objects.create(name="Acme A.Ş.", party_type=Party.CUSTOMER)
        self.invoice = Invoice.objects.create(
            party=self.customer,
            issue_date="2026-01-01",
            due_date="2026-01-31",
        )
        InvoiceLine.objects.create(
            invoice=self.invoice, description="Danışmanlık", quantity=Decimal("10"), unit_price=Decimal("100.00")
        )

    def test_total_reflects_line_amounts(self):
        self.assertEqual(self.invoice.total, Decimal("1000.00"))
        self.assertEqual(self.invoice.balance_due, Decimal("1000.00"))

    def test_cannot_send_a_document_with_no_lines(self):
        empty = Invoice.objects.create(party=self.customer, issue_date="2026-01-01", due_date="2026-01-31")
        with self.assertRaises(ValidationError):
            empty.mark_sent()

    def test_send_moves_draft_to_sent(self):
        self.invoice.mark_sent()
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.SENT)

    def test_cannot_send_twice(self):
        self.invoice.mark_sent()
        with self.assertRaises(ValidationError):
            self.invoice.mark_sent()

    def test_partial_payment_sets_status_partially_paid(self):
        self.invoice.mark_sent()
        Payment.objects.create(invoice=self.invoice, amount=Decimal("400.00"), date="2026-01-15")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.PARTIALLY_PAID)
        self.assertEqual(self.invoice.balance_due, Decimal("600.00"))

    def test_full_payment_sets_status_paid(self):
        self.invoice.mark_sent()
        Payment.objects.create(invoice=self.invoice, amount=Decimal("1000.00"), date="2026-01-15")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.PAID)
        self.assertEqual(self.invoice.balance_due, Decimal("0.00"))

    def test_multiple_partial_payments_accumulate(self):
        self.invoice.mark_sent()
        Payment.objects.create(invoice=self.invoice, amount=Decimal("300.00"), date="2026-01-10")
        Payment.objects.create(invoice=self.invoice, amount=Decimal("300.00"), date="2026-01-20")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal("600.00"))
        self.assertEqual(self.invoice.status, Invoice.PARTIALLY_PAID)

    def test_draft_is_never_auto_transitioned_by_recompute(self):
        # A payment shouldn't be recordable against a draft in normal use,
        # but recompute_status() itself must still refuse to move a draft --
        # defense in depth, not just UI-level prevention.
        self.invoice.recompute_status()
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.DRAFT)


class PaymentValidationTests(TenantTestCase):
    def setUp(self):
        self.customer = Party.objects.create(name="Acme A.Ş.", party_type=Party.CUSTOMER)
        self.vendor = Party.objects.create(name="Tedarikçi Ltd.", party_type=Party.VENDOR)
        self.invoice = Invoice.objects.create(party=self.customer, issue_date="2026-01-01", due_date="2026-01-31")
        InvoiceLine.objects.create(invoice=self.invoice, description="x", quantity=1, unit_price=Decimal("100.00"))
        self.invoice.mark_sent()

        self.bill = Bill.objects.create(party=self.vendor, issue_date="2026-01-01", due_date="2026-01-31")
        BillLine.objects.create(bill=self.bill, description="y", quantity=1, unit_price=Decimal("50.00"))
        self.bill.mark_sent()

    def test_payment_must_apply_to_exactly_one_target(self):
        with self.assertRaises(ValidationError):
            Payment.objects.create(amount=Decimal("10.00"), date="2026-01-15")  # neither set

        with self.assertRaises(ValidationError):
            Payment(
                invoice=self.invoice, bill=self.bill, amount=Decimal("10.00"), date="2026-01-15"
            ).save()  # both set

    def test_bill_payment_updates_ap_balance(self):
        Payment.objects.create(bill=self.bill, amount=Decimal("50.00"), date="2026-01-15")
        self.bill.refresh_from_db()
        self.assertEqual(self.bill.status, Bill.PAID)
        self.assertEqual(self.bill.balance_due, Decimal("0.00"))


class AgingReportAPITests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="x")
        self.customer = Party.objects.create(name="Acme A.Ş.", party_type=Party.CUSTOMER)

        today = timezone.localdate()
        self.overdue_invoice = Invoice.objects.create(
            party=self.customer, issue_date=today - timedelta(days=60), due_date=today - timedelta(days=45)
        )
        InvoiceLine.objects.create(
            invoice=self.overdue_invoice, description="x", quantity=1, unit_price=Decimal("500.00")
        )
        self.overdue_invoice.mark_sent()

        self.current_invoice = Invoice.objects.create(
            party=self.customer, issue_date=today, due_date=today + timedelta(days=30)
        )
        InvoiceLine.objects.create(
            invoice=self.current_invoice, description="y", quantity=1, unit_price=Decimal("200.00")
        )
        self.current_invoice.mark_sent()

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_aging_buckets_and_precise_decimals(self):
        response = self.client.get("/api/v1/core/reports/ar-aging/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"500.00"', response.content)  # not a bare float

        by_id = {row["document_id"]: row for row in response.data}
        self.assertEqual(by_id[self.overdue_invoice.id]["bucket"], "31-60")
        self.assertEqual(by_id[self.current_invoice.id]["bucket"], "current")

    def test_paid_invoices_are_excluded_from_aging(self):
        Payment.objects.create(invoice=self.overdue_invoice, amount=Decimal("500.00"), date=timezone.localdate())
        response = self.client.get("/api/v1/core/reports/ar-aging/", HTTP_HOST="tenant.test.com")
        ids = [row["document_id"] for row in response.data]
        self.assertNotIn(self.overdue_invoice.id, ids)
