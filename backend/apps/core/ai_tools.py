"""
Core's read-only AI metrics and chartable series (technical.md §8.2).
Registered into apps.ai_core's shared registries from CoreConfig.ready()
-- see apps/core/apps.py. Writes are not registered here: the assistant
proposes any action in the catalog through apps.ai_core.tools.
"""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.ai_core.reporting import register_series
from apps.ai_core.semantic import format_money, register_metric

from .models import Account, Bill, Invoice, JournalEntry, JournalLine
from .views import _build_aging_rows

# Tekdüzen Hesap Planı cash/bank account codes (see
# management/commands/seed_chart_of_accounts.py) -- Turkey-specific today,
# same as the rest of the seeded COA; a non-Turkey localization pack would
# need its own mapping here (technical.md §7 pattern).
CASH_ACCOUNT_CODES = ["100", "102"]


@register_metric(
    name="cash_position",
    requires="trial_balance.view",
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
    requires="ar_aging.view",
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
    requires="ap_aging.view",
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


@register_metric(
    name="flagged_vendor_bills",
    requires="bill.view",
    description="Recent vendor bills whose amount is 40%+ above that vendor's historical average -- surfaced proactively, review before approving (REQ-BI-004).",
    input_schema={"type": "object", "properties": {}},
)
def flagged_vendor_bills(**_kwargs) -> dict:
    recent = Bill.objects.filter(status__in=[Bill.DRAFT, Bill.SENT, Bill.PARTIALLY_PAID]).select_related("party").prefetch_related("lines")
    flagged = [{"bill_id": b.id, "party": b.party.name, "total": format_money(b.total), "warning": b.anomaly_warning} for b in recent if b.anomaly_warning]
    return {
        "result": {"count": len(flagged), "bills": flagged},
        "citations": [{"label": "Alış Faturaları / Bills", "route": "/bills"}],
    }


def _month_bucket(date) -> str:
    return f"{date.year:04d}-{date.month:02d}"


def _months_back(from_date, months: int):
    """`from_date` minus `months` calendar months, clamped to the 1st (bucket
    boundaries only need year/month, not the exact day)."""
    total = from_date.year * 12 + (from_date.month - 1) - months
    return total // 12, total % 12 + 1


@register_series(
    name="monthly_revenue",
    requires="trial_balance.view",
    description="Posted revenue (credit minus debit across Revenue-type accounts), bucketed by calendar month, for the last N months.",
    input_schema={"type": "object", "properties": {"months": {"type": "integer", "default": 12}}},
    chart_kind="time",
)
def monthly_revenue(months=12, **_kwargs) -> dict:
    months = int(months)
    today = timezone.localdate()
    start_year, start_month = _months_back(today, months - 1)
    lines = JournalLine.objects.filter(
        account__account_type=Account.REVENUE,
        journal_entry__status=JournalEntry.POSTED,
        journal_entry__date__year__gte=start_year,
    ).select_related("journal_entry")

    buckets: dict[str, Decimal] = defaultdict(Decimal)
    for line in lines:
        date = line.journal_entry.date
        if (date.year, date.month) < (start_year, start_month):
            continue
        buckets[_month_bucket(date)] += line.credit - line.debit

    ordered_keys = []
    for i in range(months):
        y, m = _months_back(today, months - 1 - i)
        ordered_keys.append(f"{y:04d}-{m:02d}")

    return {
        "result": {"series": [{"label": key, "value": format_money(buckets.get(key, Decimal("0")))} for key in ordered_keys]},
        "citations": [{"label": "Mizan / Trial Balance", "route": "/trial-balance"}],
    }


@register_series(
    name="revenue_by_customer",
    requires="invoice.view",
    description="Total invoiced amount per customer (sent/partially paid/paid invoices), highest first, top N customers.",
    input_schema={"type": "object", "properties": {"top_n": {"type": "integer", "default": 10}}},
    chart_kind="category",
)
def revenue_by_customer(top_n=10, **_kwargs) -> dict:
    top_n = int(top_n)
    invoices = Invoice.objects.filter(
        status__in=[Invoice.SENT, Invoice.PARTIALLY_PAID, Invoice.PAID]
    ).select_related("party").prefetch_related("lines")
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for invoice in invoices:
        totals[invoice.party.name] += invoice.total

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:top_n]
    return {
        "result": {"series": [{"label": name, "value": format_money(total)} for name, total in ranked]},
        "citations": [{"label": "Satış Faturaları / Invoices", "route": "/invoices"}],
    }


@register_series(
    name="spend_by_vendor",
    requires="bill.view",
    description="Total billed amount per vendor (sent/partially paid/paid bills), highest first, top N vendors.",
    input_schema={"type": "object", "properties": {"top_n": {"type": "integer", "default": 10}}},
    chart_kind="category",
)
def spend_by_vendor(top_n=10, **_kwargs) -> dict:
    top_n = int(top_n)
    bills = Bill.objects.filter(
        status__in=[Bill.SENT, Bill.PARTIALLY_PAID, Bill.PAID]
    ).select_related("party").prefetch_related("lines")
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for bill in bills:
        totals[bill.party.name] += bill.total

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:top_n]
    return {
        "result": {"series": [{"label": name, "value": format_money(total)} for name, total in ranked]},
        "citations": [{"label": "Alış Faturaları / Bills", "route": "/bills"}],
    }
