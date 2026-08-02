"""
Core's read-only AI metrics and write actions (technical.md §8.2/§8.4).
Registered into apps.ai_core's shared registries from CoreConfig.ready()
-- see apps/core/apps.py.
"""

from decimal import Decimal
from types import SimpleNamespace

from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.ai_core.actions import register_action
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


def _journal_entry_preview(entity=None, date=None, memo="", lines=None, **_kwargs) -> str:
    """Read-only -- looks up account codes for a friendlier preview, but
    never writes anything. Falls back to raw ids if a lookup fails, since
    the preview must never itself error out and block showing the approval
    prompt."""
    line_descriptions = []
    for line in lines or []:
        try:
            account = Account.objects.get(id=line.get("account_id"))
            label = f"{account.code} — {account.name}"
        except Account.DoesNotExist:
            label = f"hesap #{line.get('account_id')}"
        debit, credit = line.get("debit", "0"), line.get("credit", "0")
        line_descriptions.append(f"{label}: borç {debit} / alacak {credit}")
    lines_text = "; ".join(line_descriptions) if line_descriptions else "(satır yok)"
    return f"{date} tarihli, '{memo or 'açıklama yok'}' açıklamalı bir TASLAK yevmiye kaydı oluşturulacak: {lines_text}"


@register_action(
    name="create_journal_entry",
    description=(
        "Create a DRAFT journal entry (not posted -- the user must still review and post it from the "
        "Journal Entries screen). Every line's account must belong to the given entity's own Chart of "
        "Accounts, and total debits must equal total credits."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "entity": {"type": "integer", "description": "The entity id this journal entry's ledger belongs to."},
            "date": {"type": "string", "description": "YYYY-MM-DD"},
            "memo": {"type": "string"},
            "lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "integer"},
                        "debit": {"type": "string"},
                        "credit": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["account_id", "debit", "credit"],
                },
            },
        },
        "required": ["entity", "date", "lines"],
    },
    preview=_journal_entry_preview,
)
def create_journal_entry(user, entity=None, date=None, memo="", lines=None) -> dict:
    # Reuses JournalEntrySerializer itself for validation/creation --
    # technical.md §8.4: "a thin wrapper around the same service-layer call
    # the API view uses, not a separate code path with its own (possibly
    # weaker) authorization logic." SimpleNamespace stands in for a real
    # DRF Request here since the serializer only ever reads `.user` off it.
    from .serializers import JournalEntrySerializer

    payload = {
        "entity": entity,
        "date": date,
        "memo": memo or "",
        "lines": [
            {
                "account": line.get("account_id"),
                "debit": line.get("debit", "0"),
                "credit": line.get("credit", "0"),
                "description": line.get("description", ""),
            }
            for line in (lines or [])
        ],
    }
    serializer = JournalEntrySerializer(data=payload, context={"request": SimpleNamespace(user=user)})
    try:
        serializer.is_valid(raise_exception=True)
    except DRFValidationError as exc:
        raise ValueError(str(exc.detail)) from exc
    entry = serializer.save()
    return {
        "result": {"id": entry.id, "status": entry.status, "entity": entity},
        "summary": f"Draft journal entry #{entry.id} created for {entry.date} -- not yet posted.",
    }
