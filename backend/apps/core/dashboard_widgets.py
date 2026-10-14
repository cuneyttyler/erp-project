"""
Core's home-panel widgets (REQ-CORE-RPT-001) for the General Ledger,
Receivables & Payables and Item Catalog plugins, plus the plugin-independent
activity feed. Registered into apps.plugins' registry from
CoreConfig.ready() -- see apps/core/apps.py.

Money totals follow the same rule as the rest of this app: a Sum() is only
taken over a single table (JournalLine); invoice/bill totals go through
`_build_aging_rows` / the model properties over prefetched rows, never a
lines-and-payments join (see FinancialDocument's docstring).
"""

import datetime
from collections import defaultdict
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.access.permissions import is_org_admin
from apps.plugins import registry as r
from apps.plugins.periods import month_key, month_starts

from .ai_tools import CASH_ACCOUNT_CODES
from .models import Account, AuditLogEntry, Bill, Invoice, Item, JournalEntry, JournalLine, Payment, User
from .views import _build_aging_rows

ZERO = Decimal("0")


# --------------------------------------------------------------------------
# General Ledger
# --------------------------------------------------------------------------
def _posted_lines(ctx: r.WidgetContext):
    lines = JournalLine.objects.filter(journal_entry__status=JournalEntry.POSTED)
    if ctx.entity_id:
        lines = lines.filter(journal_entry__entity_id=ctx.entity_id)
    return lines


def _monthly_pnl(ctx: r.WidgetContext, months: int) -> list[dict]:
    """Posted revenue and expense per calendar month, oldest first, ending
    with the current month. Revenue is credit minus debit on Revenue-type
    accounts; expense is debit minus credit on Expense-type accounts."""
    starts = month_starts(months)
    rows = (
        _posted_lines(ctx)
        .filter(journal_entry__date__gte=starts[0], account__account_type__in=[Account.REVENUE, Account.EXPENSE])
        .annotate(month=TruncMonth("journal_entry__date"))
        .values("month", "account__account_type")
        .annotate(debit_sum=Sum("debit"), credit_sum=Sum("credit"))
    )
    by_month: dict[str, dict] = defaultdict(lambda: {"revenue": ZERO, "expense": ZERO})
    for row in rows:
        debit, credit = row["debit_sum"] or ZERO, row["credit_sum"] or ZERO
        bucket = by_month[month_key(row["month"])]
        if row["account__account_type"] == Account.REVENUE:
            bucket["revenue"] += credit - debit
        else:
            bucket["expense"] += debit - credit
    result = []
    for start in starts:
        bucket = by_month[month_key(start)]
        result.append({"month": month_key(start), **bucket, "net": bucket["revenue"] - bucket["expense"]})
    return result


def _month_to_date_stat(ctx: r.WidgetContext, field: str, good_when: str) -> dict:
    months = _monthly_pnl(ctx, 6)
    current, previous = months[-1][field], months[-2][field]
    return r.stat(
        current,
        delta=r.delta(current, previous, "vs_last_month", good_when=good_when),
        trend=[{"label": m["month"], "value": str(m[field])} for m in months],
        route="/trial-balance",
    )


@r.register_widget("cash_position", plugin="general_ledger", kind=r.STAT, order=100)
def cash_position(ctx: r.WidgetContext) -> dict:
    """Cash + bank balance today, with the month-end balance for each of
    the last six months as the trend."""
    cash_lines = _posted_lines(ctx).filter(account__code__in=CASH_ACCOUNT_CODES)
    starts = month_starts(6)
    opening = cash_lines.filter(journal_entry__date__lt=starts[0]).aggregate(d=Sum("debit"), c=Sum("credit"))
    balance = (opening["d"] or ZERO) - (opening["c"] or ZERO)
    movement = {
        month_key(row["month"]): (row["d"] or ZERO) - (row["c"] or ZERO)
        for row in cash_lines.filter(journal_entry__date__gte=starts[0])
        .annotate(month=TruncMonth("journal_entry__date"))
        .values("month")
        .annotate(d=Sum("debit"), c=Sum("credit"))
    }
    trend = []
    for start in starts:
        balance += movement.get(month_key(start), ZERO)
        trend.append({"label": month_key(start), "value": str(balance)})
    return r.stat(
        balance,
        secondary=[r.secondary("change_this_month", movement.get(month_key(starts[-1]), ZERO), "money")],
        trend=trend,
        route="/trial-balance",
    )


@r.register_widget("revenue_mtd", plugin="general_ledger", kind=r.STAT, order=110)
def revenue_mtd(ctx: r.WidgetContext) -> dict:
    return _month_to_date_stat(ctx, "revenue", good_when="up")


@r.register_widget("expenses_mtd", plugin="general_ledger", kind=r.STAT, order=120)
def expenses_mtd(ctx: r.WidgetContext) -> dict:
    return _month_to_date_stat(ctx, "expense", good_when="down")


@r.register_widget("net_income_mtd", plugin="general_ledger", kind=r.STAT, order=130)
def net_income_mtd(ctx: r.WidgetContext) -> dict:
    return _month_to_date_stat(ctx, "net", good_when="up")


@r.register_widget("revenue_expense_trend", plugin="general_ledger", kind=r.CHART, order=300)
def revenue_expense_trend(ctx: r.WidgetContext) -> dict:
    months = _monthly_pnl(ctx, 12)
    return r.chart(
        "line",
        [
            r.series("revenue", [(m["month"], m["revenue"]) for m in months]),
            r.series("expenses", [(m["month"], m["expense"]) for m in months]),
        ],
        label_kind="month",
        route="/trial-balance",
    )


@r.register_widget("expense_breakdown", plugin="general_ledger", kind=r.CHART, order=380, default_enabled=False)
def expense_breakdown(ctx: r.WidgetContext) -> dict:
    """The largest expense accounts so far this calendar year."""
    year_start = datetime.date(timezone.localdate().year, 1, 1)
    rows = (
        _posted_lines(ctx)
        .filter(account__account_type=Account.EXPENSE, journal_entry__date__gte=year_start)
        .values("account__code", "account__name")
        .annotate(d=Sum("debit"), c=Sum("credit"))
    )
    totals = [(f"{row['account__code']} — {row['account__name']}", (row["d"] or ZERO) - (row["c"] or ZERO)) for row in rows]
    ranked = sorted((t for t in totals if t[1] > 0), key=lambda t: t[1], reverse=True)[:6]
    return r.chart("hbar", [r.series("amount", ranked)], route="/trial-balance")


@r.register_widget("recent_journal_entries", plugin="general_ledger", kind=r.TABLE, order=410, default_enabled=False)
def recent_journal_entries(ctx: r.WidgetContext) -> dict:
    entries = JournalEntry.objects.annotate(amount=Sum("lines__debit"))
    if ctx.entity_id:
        entries = entries.filter(entity_id=ctx.entity_id)
    rows = [
        {"date": str(e.date), "memo": e.memo, "status": e.status, "amount": str(e.amount or ZERO)}
        for e in entries[:8]
    ]
    return r.table(
        [("date", "date"), ("memo", "text"), ("status", "status"), ("amount", "money")],
        rows,
        route="/journal-entries",
        total_count=entries.count(),
    )


@r.register_attention("general_ledger")
def _ledger_attention(ctx: r.WidgetContext) -> list:
    drafts = JournalEntry.objects.filter(status=JournalEntry.DRAFT)
    if ctx.entity_id:
        drafts = drafts.filter(entity_id=ctx.entity_id)
    return [r.attention_item("draft_journal_entries", drafts.count(), r.INFO, "/journal-entries")]


# --------------------------------------------------------------------------
# Receivables & Payables
# --------------------------------------------------------------------------
AGING_BUCKETS = [("current", "current"), ("1-30", "d1_30"), ("31-60", "d31_60"), ("61-90", "d61_90"), ("90+", "d90_plus")]


def _open_rows(model, ctx: r.WidgetContext) -> list[dict]:
    """Aging rows (one per document with a balance still due) for every
    sent/partially-paid Invoice or Bill."""
    docs = model.objects.filter(status__in=[model.SENT, model.PARTIALLY_PAID]).select_related("party").prefetch_related("lines", "payments")
    if ctx.entity_id:
        docs = docs.filter(party__entity_id=ctx.entity_id)
    return _build_aging_rows(docs)


def _total(rows: list[dict]) -> Decimal:
    return sum((row["balance_due"] for row in rows), ZERO)


def _outstanding_stat(model, ctx: r.WidgetContext, route: str) -> dict:
    rows = _open_rows(model, ctx)
    overdue = [row for row in rows if row["days_overdue"] > 0]
    return r.stat(
        _total(rows),
        secondary=[r.secondary("overdue", _total(overdue), "money"), r.secondary("open_documents", len(rows))],
        route=route,
    )


def _aging_chart(model, ctx: r.WidgetContext) -> dict:
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in _open_rows(model, ctx):
        totals[row["bucket"]] += row["balance_due"]
    return r.chart("bar", [r.series("balance", [(label, totals[bucket]) for bucket, label in AGING_BUCKETS])], label_kind="key", route="/aging")


@r.register_widget("ar_outstanding", plugin="receivables_payables", kind=r.STAT, order=140)
def ar_outstanding(ctx: r.WidgetContext) -> dict:
    return _outstanding_stat(Invoice, ctx, "/invoices")


@r.register_widget("ap_outstanding", plugin="receivables_payables", kind=r.STAT, order=150)
def ap_outstanding(ctx: r.WidgetContext) -> dict:
    return _outstanding_stat(Bill, ctx, "/bills")


@r.register_widget("ar_aging", plugin="receivables_payables", kind=r.CHART, order=320)
def ar_aging(ctx: r.WidgetContext) -> dict:
    return _aging_chart(Invoice, ctx)


@r.register_widget("ap_aging", plugin="receivables_payables", kind=r.CHART, order=330, default_enabled=False)
def ap_aging(ctx: r.WidgetContext) -> dict:
    return _aging_chart(Bill, ctx)


@r.register_widget("cash_forecast", plugin="receivables_payables", kind=r.CHART, order=310)
def cash_forecast(ctx: r.WidgetContext) -> dict:
    """Open receivables (money in) against open payables (money out) by the
    week they fall due, for the next four weeks -- with everything already
    past due in its own leading bucket rather than silently dropped."""
    today = timezone.localdate()
    week_starts = [today + datetime.timedelta(days=7 * i) for i in range(4)]
    labels = ["overdue"] + [str(start) for start in week_starts]

    def bucketed(rows: list[dict]) -> list[tuple]:
        totals = [ZERO] * len(labels)
        for row in rows:
            days_ahead = (row["due_date"] - today).days
            if days_ahead < 0:
                totals[0] += row["balance_due"]
            elif days_ahead < 28:
                totals[1 + days_ahead // 7] += row["balance_due"]
        return list(zip(labels, totals))

    return r.chart(
        "bar",
        [r.series("inflow", bucketed(_open_rows(Invoice, ctx))), r.series("outflow", bucketed(_open_rows(Bill, ctx)))],
        label_kind="date",
        route="/aging",
    )


@r.register_widget("overdue_invoices", plugin="receivables_payables", kind=r.TABLE, order=340)
def overdue_invoices(ctx: r.WidgetContext) -> dict:
    overdue = [row for row in _open_rows(Invoice, ctx) if row["days_overdue"] > 0]
    overdue.sort(key=lambda row: row["balance_due"], reverse=True)
    rows = [
        {"party": row["party_name"], "due_date": str(row["due_date"]), "days_overdue": row["days_overdue"], "balance_due": str(row["balance_due"])}
        for row in overdue[:8]
    ]
    return r.table(
        [("party", "text"), ("due_date", "date"), ("days_overdue", "number"), ("balance_due", "money")],
        rows,
        route="/aging",
        total_count=len(overdue),
    )


BILLS_DUE_SOON_DAYS = 14


@r.register_widget("upcoming_bills", plugin="receivables_payables", kind=r.TABLE, order=350)
def upcoming_bills(ctx: r.WidgetContext) -> dict:
    """Bills to pay: everything overdue plus everything due in the next
    two weeks, soonest first."""
    horizon = timezone.localdate() + datetime.timedelta(days=BILLS_DUE_SOON_DAYS)
    due = sorted((row for row in _open_rows(Bill, ctx) if row["due_date"] <= horizon), key=lambda row: row["due_date"])
    rows = [
        {
            "party": row["party_name"],
            "due_date": str(row["due_date"]),
            "status": "overdue" if row["days_overdue"] > 0 else "due_soon",
            "balance_due": str(row["balance_due"]),
        }
        for row in due[:8]
    ]
    return r.table(
        [("party", "text"), ("due_date", "date"), ("status", "status"), ("balance_due", "money")],
        rows,
        route="/bills",
        total_count=len(due),
    )


def _top_parties(model, ctx: r.WidgetContext, route: str) -> dict:
    docs = model.objects.filter(status__in=[model.SENT, model.PARTIALLY_PAID, model.PAID]).select_related("party").prefetch_related("lines")
    if ctx.entity_id:
        docs = docs.filter(party__entity_id=ctx.entity_id)
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for doc in docs:
        totals[doc.party.name] += doc.total
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:6]
    return r.chart("hbar", [r.series("amount", ranked)], route=route)


@r.register_widget("top_customers", plugin="receivables_payables", kind=r.CHART, order=360)
def top_customers(ctx: r.WidgetContext) -> dict:
    return _top_parties(Invoice, ctx, "/invoices")


@r.register_widget("top_vendors", plugin="receivables_payables", kind=r.CHART, order=370, default_enabled=False)
def top_vendors(ctx: r.WidgetContext) -> dict:
    return _top_parties(Bill, ctx, "/bills")


def _flagged_bills(ctx: r.WidgetContext) -> list[Bill]:
    """Unpaid bills well above their vendor's historical average
    (REQ-BI-004, `Bill.anomaly_warning`)."""
    bills = Bill.objects.filter(status__in=[Bill.DRAFT, Bill.SENT, Bill.PARTIALLY_PAID]).select_related("party").prefetch_related("lines")
    if ctx.entity_id:
        bills = bills.filter(party__entity_id=ctx.entity_id)
    return [bill for bill in bills if bill.anomaly_warning]


@r.register_widget("flagged_bills", plugin="receivables_payables", kind=r.TABLE, order=390, default_enabled=False)
def flagged_bills(ctx: r.WidgetContext) -> dict:
    flagged = _flagged_bills(ctx)
    rows = [
        {"party": bill.party.name, "issue_date": str(bill.issue_date), "status": bill.status, "total": str(bill.total)}
        for bill in flagged[:8]
    ]
    return r.table(
        [("party", "text"), ("issue_date", "date"), ("status", "status"), ("total", "money")],
        rows,
        route="/bills",
        total_count=len(flagged),
    )


@r.register_widget("recent_payments", plugin="receivables_payables", kind=r.TABLE, order=400, default_enabled=False)
def recent_payments(ctx: r.WidgetContext) -> dict:
    payments = Payment.objects.select_related("invoice__party", "bill__party")
    if ctx.entity_id:
        payments = payments.filter(Q(invoice__party__entity_id=ctx.entity_id) | Q(bill__party__entity_id=ctx.entity_id))
    rows = [
        {
            "date": str(p.date),
            "party": (p.invoice or p.bill).party.name,
            "direction": "received" if p.invoice_id else "paid",
            "method": p.method,
            "amount": str(p.amount),
        }
        for p in payments[:8]
    ]
    return r.table(
        [("date", "date"), ("party", "text"), ("direction", "status"), ("method", "text"), ("amount", "money")],
        rows,
        route="/invoices",
        total_count=payments.count(),
    )


BILLS_ATTENTION_DAYS = 7


@r.register_attention("receivables_payables")
def _arap_attention(ctx: r.WidgetContext) -> list:
    today = timezone.localdate()
    invoices, bills = _open_rows(Invoice, ctx), _open_rows(Bill, ctx)
    overdue_invoices_ = [row for row in invoices if row["days_overdue"] > 0]
    overdue_bills = [row for row in bills if row["days_overdue"] > 0]
    due_soon = [row for row in bills if 0 <= (row["due_date"] - today).days <= BILLS_ATTENTION_DAYS]
    return [
        r.attention_item("overdue_invoices", len(overdue_invoices_), r.CRITICAL, "/aging", _total(overdue_invoices_)),
        r.attention_item("overdue_bills", len(overdue_bills), r.CRITICAL, "/aging", _total(overdue_bills)),
        r.attention_item("bills_due_soon", len(due_soon), r.WARNING, "/bills", _total(due_soon)),
        r.attention_item("flagged_bills", len(_flagged_bills(ctx)), r.WARNING, "/bills"),
    ]


# --------------------------------------------------------------------------
# Item Catalog
# --------------------------------------------------------------------------
@r.register_widget("catalog_summary", plugin="item_catalog", kind=r.STAT, order=220, default_enabled=False)
def catalog_summary(ctx: r.WidgetContext) -> dict:
    active = Item.objects.filter(is_active=True).count()
    inactive = Item.objects.filter(is_active=False).count()
    return r.stat(active, "number", secondary=[r.secondary("inactive_items", inactive)], route="/items")


# --------------------------------------------------------------------------
# Activity (no plugin -- always available)
# --------------------------------------------------------------------------
@r.register_widget("recent_activity", plugin=None, kind=r.TABLE, order=910, default_enabled=False)
def recent_activity(ctx: r.WidgetContext) -> dict:
    """The newest audit-trail entries (REQ-CORE-AUDIT-001). `actor` is
    stored as "user:<id>" / "ai:<id>" -- resolved to a username here so the
    panel doesn't show raw ids."""
    # Same rule as the audit log page, kept simple for a ten-row widget:
    # an admin sees everyone's actions, anyone else their own.
    visible = AuditLogEntry.objects.all() if is_org_admin(ctx.user) else AuditLogEntry.objects.filter(user=ctx.user)
    entries = list(visible[:10])
    actor_ids = {e.actor.split(":", 1)[1] for e in entries if ":" in e.actor}
    usernames = {str(u.id): u.username for u in User.objects.filter(id__in=[i for i in actor_ids if i.isdigit()])}

    def actor_label(actor: str) -> str:
        kind, _, actor_id = actor.partition(":")
        name = usernames.get(actor_id, actor_id)
        return f"{name} (AI)" if kind == "ai" else name

    rows = [
        {
            "created_at": e.created_at.isoformat(),
            "actor": actor_label(e.actor),
            "action": e.action,
            "target": f"{e.target_type} #{e.target_id}",
        }
        for e in entries
    ]
    return r.table(
        [("created_at", "datetime"), ("actor", "text"), ("action", "text"), ("target", "text")],
        rows,
        total_count=visible.count(),
    )
