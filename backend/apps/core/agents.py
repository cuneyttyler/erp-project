"""
First agentic workflow preview (development-plan.md §5's Phase 2 AI line
item: "first agentic workflows (e.g., reconciliation sweep) as a preview
of the Phase 3 Agents Pack"). REQ-AIAGENT-001/002/003 -- a general
scheduled/trigger-based workflow *framework*, a low-code definition UI, and
an activity dashboard -- are Phase 3 scope in full; this is one concrete,
real, hard-coded workflow proving the shape works end to end, not that
framework.

What's real here: the sweep logic itself, and that every run writes a real
audit trail entry. What's NOT wired up (see docs/notes.md): a Celery beat
schedule to actually run this unattended on a cadence -- `apps/core/tasks.py`
has the Celery task ready to be scheduled, and `run_reconciliation_sweep`
(management command) lets it be triggered by hand or by an external cron in
the meantime, but no beat schedule entry exists yet in this dev environment.
"""

from decimal import Decimal

from django.utils import timezone

from .models import AuditLogEntry, Invoice
from .views import _build_aging_rows


def run_ar_reconciliation_sweep(threshold_days: int = 30) -> dict:
    """
    Flags every open customer invoice overdue by more than `threshold_days`
    across every entity in the current tenant schema. Purely read-only
    against the invoices themselves -- the only side effect is the audit
    log entry recording what it found, so re-running it is always safe
    (idempotent in effect, even though it isn't literally a no-op).
    """
    queryset = (
        Invoice.objects.filter(status__in=[Invoice.SENT, Invoice.PARTIALLY_PAID])
        .select_related("party", "party__entity")
        .prefetch_related("lines", "payments")
    )
    rows = [r for r in _build_aging_rows(queryset) if r["days_overdue"] > threshold_days]
    total_overdue = sum((r["balance_due"] for r in rows), Decimal("0"))

    summary = {
        "threshold_days": threshold_days,
        "flagged_count": len(rows),
        "total_overdue": str(total_overdue),
        "flagged": [
            {
                "document_id": r["document_id"],
                "party_name": r["party_name"],
                "days_overdue": r["days_overdue"],
                "balance_due": str(r["balance_due"]),
            }
            for r in rows
        ],
        "run_at": timezone.now().isoformat(),
    }

    # REQ-CORE-AI-008 applies to agentic/scheduled actions the same as
    # chat-initiated ones -- "ai:system" since no human user triggered this
    # particular run (distinct from "ai:<user_id>" used elsewhere for
    # chat-originated audit rows).
    AuditLogEntry.objects.create(
        actor="ai:system",
        action="ai_agentic_ar_reconciliation_sweep",
        target_type="sweep",
        target_id=timezone.now().strftime("%Y%m%dT%H%M%S%f"),
        before={"threshold_days": threshold_days},
        after=summary,
    )
    return summary
