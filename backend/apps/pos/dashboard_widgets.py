"""POS / Retail's home-panel widgets. Registered from PosConfig.ready().

"Sales" here is net of returns: each day's sale lines (quantity x unit
price, less line discounts) minus the refunds issued that day. Both sides
are single-table Sum()s -- sale lines and return lines are never joined."""

import datetime
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.plugins import registry as r
from apps.plugins.periods import last_days

from .models import POSPayment, POSReturnLine, POSSale, POSSaleLine, POSShift

ZERO = Decimal("0")
STALE_SHIFT_HOURS = 24


def _daily_net_sales(since: datetime.date) -> dict[datetime.date, Decimal]:
    sold = (
        POSSaleLine.objects.filter(sale__created_at__date__gte=since)
        .annotate(day=TruncDate("sale__created_at"))
        .values("day")
        .annotate(total=Sum(F("quantity") * F("unit_price") - F("discount_amount")))
    )
    refunded = (
        POSReturnLine.objects.filter(pos_return__created_at__date__gte=since)
        .annotate(day=TruncDate("pos_return__created_at"))
        .values("day")
        .annotate(total=Sum("refund_amount"))
    )
    totals: dict[datetime.date, Decimal] = {}
    for row in sold:
        totals[row["day"]] = totals.get(row["day"], ZERO) + (row["total"] or ZERO)
    for row in refunded:
        totals[row["day"]] = totals.get(row["day"], ZERO) - (row["total"] or ZERO)
    return totals


@r.register_widget("pos_sales_today", plugin="pos", kind=r.STAT, order=200)
def pos_sales_today(ctx: r.WidgetContext) -> dict:
    days = last_days(7)
    totals = _daily_net_sales(days[0])
    today, yesterday = totals.get(days[-1], ZERO), totals.get(days[-2], ZERO)
    return r.stat(
        today,
        secondary=[
            r.secondary("transactions", POSSale.objects.filter(created_at__date=days[-1]).count()),
            r.secondary("open_shifts", POSShift.objects.filter(status=POSShift.OPEN).count()),
        ],
        delta=r.delta(today, yesterday, "vs_yesterday"),
        trend=[{"label": str(day), "value": str(totals.get(day, ZERO))} for day in days],
        route="/pos/shifts",
    )


@r.register_widget("pos_sales_trend", plugin="pos", kind=r.CHART, order=750)
def pos_sales_trend(ctx: r.WidgetContext) -> dict:
    days = last_days(14)
    totals = _daily_net_sales(days[0])
    return r.chart("line", [r.series("net_sales", [(day, totals.get(day, ZERO)) for day in days])], label_kind="date", route="/pos/shifts")


@r.register_widget("open_shifts", plugin="pos", kind=r.TABLE, order=760, default_enabled=False)
def open_shifts(ctx: r.WidgetContext) -> dict:
    shifts = (
        POSShift.objects.filter(status=POSShift.OPEN)
        .select_related("till__store", "opened_by")
        .annotate(sale_count=Count("sales"))
        .order_by("opened_at")
    )
    rows = [
        {
            "store": shift.till.store.name,
            "till": shift.till.name,
            "opened_by": shift.opened_by.username,
            "opened_at": shift.opened_at.isoformat(),
            "sales": shift.sale_count,
        }
        for shift in shifts[:8]
    ]
    return r.table(
        [("store", "text"), ("till", "text"), ("opened_by", "text"), ("opened_at", "datetime"), ("sales", "number")],
        rows,
        route="/pos/shifts",
        total_count=shifts.count(),
    )


@r.register_widget("pos_top_items", plugin="pos", kind=r.CHART, order=770, default_enabled=False)
def pos_top_items(ctx: r.WidgetContext) -> dict:
    """Best sellers by units over the last 30 days (returns netted off)."""
    since = timezone.localdate() - datetime.timedelta(days=29)
    rows = (
        POSSaleLine.objects.filter(sale__created_at__date__gte=since)
        .values("item__name")
        .annotate(units=Sum(F("quantity") - F("quantity_returned")))
        .order_by("-units")[:6]
    )
    return r.chart("hbar", [r.series("units", [(row["item__name"], row["units"] or ZERO) for row in rows])], fmt="number", route="/pos/shifts")


@r.register_attention("pos")
def _pos_attention(ctx: r.WidgetContext) -> list:
    cutoff = timezone.now() - datetime.timedelta(hours=STALE_SHIFT_HOURS)
    stale = POSShift.objects.filter(status=POSShift.OPEN, opened_at__lt=cutoff).count()
    return [r.attention_item("stale_open_shifts", stale, r.WARNING, "/pos/shifts")]


# Page charts (see apps/core/dashboard_widgets.py).
@r.register_widget("pos_sales_by_till", plugin="pos", kind=r.CHART, order=1600, default_enabled=False)
def pos_sales_by_till(ctx: r.WidgetContext) -> dict:
    """Takings per till over the last 30 days (payments received, before returns)."""
    since = timezone.localdate() - datetime.timedelta(days=29)
    rows = (
        POSPayment.objects.filter(sale__created_at__date__gte=since)
        .values("sale__shift__till__store__code", "sale__shift__till__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")[:8]
    )
    points = [(f"{row['sale__shift__till__store__code']} · {row['sale__shift__till__name']}", row["total"]) for row in rows]
    return r.chart("hbar", [r.series("amount", points)], route="/pos/shifts")


@r.register_widget("pos_payment_mix", plugin="pos", kind=r.CHART, order=1610, default_enabled=False)
def pos_payment_mix(ctx: r.WidgetContext) -> dict:
    """Cash against card over the last 30 days."""
    since = timezone.localdate() - datetime.timedelta(days=29)
    totals = dict(POSPayment.objects.filter(sale__created_at__date__gte=since).values_list("method").annotate(total=Sum("amount")))
    return r.chart(
        "hbar",
        [r.series("amount", [(method, totals.get(method, ZERO)) for method in (POSPayment.CASH, POSPayment.CARD)])],
        label_kind="key",
        route="/pos/shifts",
    )
