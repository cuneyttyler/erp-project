"""
Core's read-only AI metrics (technical.md §8.2/§8.4 pattern applied to the
read path). Registered into apps.ai_core.semantic's shared registry from
CoreConfig.ready() -- see apps/core/apps.py.
"""

from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.ai_core.semantic import format_money, register_metric

from .models import Account, Bill, Invoice, JournalEntry
from .views import _build_aging_rows

# Tekdüzen Hesap Planı cash/bank account codes (see
# management/commands/seed_chart_of_accounts.py) -- Turkey-specific today,
# same as the rest of the seeded COA; a non-Turkey localization pack would
# need its own mapping here (technical.md §7 pattern).
CASH_ACCOUNT_CODES = ["100", "102"]


@register_metric(
    name="cash_position",
    description="Current cash + bank balance (Kasa + Bankalar) across all posted journal entries.",
    input_schema={"type": "object", "properties": {}},
)
def cash_position(**_kwargs) -> dict:
    rows = Account.objects.filter(
        code__in=CASH_ACCOUNT_CODES, journal_lines__journal_entry__status=JournalEntry.POSTED
    ).aggregate(total_debit=Sum("journal_lines__debit"), total_credit=Sum("journal_lines__credit"))
    total_debit = rows["total_debit"] or Decimal("0")
    total_credit = rows["total_credit"] or Decimal("0")
    balance = total_debit - total_credit
    return {
        "result": {"as_of": str(timezone.localdate()), "cash_and_bank_balance": str(balance)},
        "citations": [{"label": "Mizan / Trial Balance", "route": "/trial-balance"}],
    }


@register_metric(
    name="overdue_ar_balance",
    description="Total overdue accounts-receivable balance (unpaid customer invoices past due date), and the top overdue customers.",
    input_schema={"type": "object", "properties": {}},
)
def overdue_ar_balance(**_kwargs) -> dict:
    queryset = Invoice.objects.filter(
        status__in=[Invoice.SENT, Invoice.PARTIALLY_PAID]
    ).select_related("party").prefetch_related("lines", "payments")
    rows = [r for r in _build_aging_rows(queryset) if r["days_overdue"] > 0]
    total = sum((r["balance_due"] for r in rows), Decimal("0"))
    top = sorted(rows, key=lambda r: r["balance_due"], reverse=True)[:5]
    return {
        "result": {
            "total_overdue": format_money(total),
            "count": len(rows),
            "top_customers": [{"party": r["party_name"], "balance_due": format_money(r["balance_due"]), "days_overdue": r["days_overdue"]} for r in top],
        },
        "citations": [{"label": "Yaşlandırma / AR Aging", "route": "/aging"}],
    }


@register_metric(
    name="overdue_ap_balance",
    description="Total overdue accounts-payable balance (unpaid vendor bills past due date), and the top overdue vendors.",
    input_schema={"type": "object", "properties": {}},
)
def overdue_ap_balance(**_kwargs) -> dict:
    queryset = Bill.objects.filter(
        status__in=[Bill.SENT, Bill.PARTIALLY_PAID]
    ).select_related("party").prefetch_related("lines", "payments")
    rows = [r for r in _build_aging_rows(queryset) if r["days_overdue"] > 0]
    total = sum((r["balance_due"] for r in rows), Decimal("0"))
    top = sorted(rows, key=lambda r: r["balance_due"], reverse=True)[:5]
    return {
        "result": {
            "total_overdue": format_money(total),
            "count": len(rows),
            "top_vendors": [{"party": r["party_name"], "balance_due": format_money(r["balance_due"]), "days_overdue": r["days_overdue"]} for r in top],
        },
        "citations": [{"label": "Yaşlandırma / AP Aging", "route": "/aging"}],
    }
