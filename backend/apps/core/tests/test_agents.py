"""Tests for the AR reconciliation sweep -- the first agentic-workflow
preview (development-plan.md §5). What matters here: it flags the right
invoices past the threshold, ignores everything else, and its only side
effect (the audit log entry) is real."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django_tenants.test.cases import TenantTestCase

from apps.core.agents import run_ar_reconciliation_sweep
from apps.core.models import AuditLogEntry, Invoice, InvoiceLine, Party


class RunArReconciliationSweepTests(TenantTestCase):
    def setUp(self):
        self.customer = Party.objects.create(name="Acme A.Ş.", party_type=Party.CUSTOMER)

    def _sent_invoice(self, days_overdue, amount):
        today = timezone.localdate()
        invoice = Invoice.objects.create(
            party=self.customer,
            issue_date=today - timedelta(days=days_overdue + 10),
            due_date=today - timedelta(days=days_overdue),
        )
        InvoiceLine.objects.create(invoice=invoice, description="x", quantity=1, unit_price=Decimal(amount))
        invoice.mark_sent()
        return invoice

    def test_flags_invoices_past_the_threshold_only(self):
        self._sent_invoice(days_overdue=40, amount="1500.00")
        self._sent_invoice(days_overdue=10, amount="500.00")

        summary = run_ar_reconciliation_sweep(threshold_days=30)

        self.assertEqual(summary["flagged_count"], 1)
        self.assertEqual(Decimal(summary["total_overdue"]), Decimal("1500.00"))
        self.assertEqual(summary["flagged"][0]["party_name"], "Acme A.Ş.")

    def test_no_invoices_past_threshold_returns_empty_summary(self):
        self._sent_invoice(days_overdue=5, amount="500.00")
        summary = run_ar_reconciliation_sweep(threshold_days=30)
        self.assertEqual(summary["flagged_count"], 0)
        self.assertEqual(summary["total_overdue"], "0")

    def test_writes_an_audit_log_entry_with_ai_system_actor(self):
        self._sent_invoice(days_overdue=40, amount="1500.00")
        run_ar_reconciliation_sweep(threshold_days=30)
        entry = AuditLogEntry.objects.get(action="ai_agentic_ar_reconciliation_sweep")
        self.assertEqual(entry.actor, "ai:system")
        self.assertEqual(entry.after["flagged_count"], 1)

    def test_is_safe_to_run_repeatedly(self):
        self._sent_invoice(days_overdue=40, amount="1500.00")
        run_ar_reconciliation_sweep(threshold_days=30)
        run_ar_reconciliation_sweep(threshold_days=30)
        self.assertEqual(AuditLogEntry.objects.filter(action="ai_agentic_ar_reconciliation_sweep").count(), 2)
