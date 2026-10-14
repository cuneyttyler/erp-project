"""Sales & CRM's home-panel widgets. Registered from SalesCrmConfig.ready()."""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count
from django.utils import timezone

from apps.plugins import registry as r
from apps.plugins.periods import month_key, month_starts

from .models import Lead, SalesOrder

ZERO = Decimal("0")
OPEN_STATUSES = [SalesOrder.CONFIRMED, SalesOrder.PARTIALLY_FULFILLED]


def _open_orders():
    return SalesOrder.objects.filter(status__in=OPEN_STATUSES).select_related("party").prefetch_related("lines")


@r.register_widget("open_sales_orders", plugin="sales_crm", kind=r.STAT, order=160)
def open_sales_orders(ctx: r.WidgetContext) -> dict:
    """Value of everything confirmed but not yet fully shipped."""
    orders = list(_open_orders())
    return r.stat(
        sum((so.total for so in orders), ZERO),
        secondary=[
            r.secondary("open_orders", len(orders)),
            r.secondary("draft_orders", SalesOrder.objects.filter(status=SalesOrder.DRAFT).count()),
        ],
        route="/sales-orders",
    )


@r.register_widget("sales_pipeline", plugin="sales_crm", kind=r.CHART, order=600)
def sales_pipeline(ctx: r.WidgetContext) -> dict:
    counts = dict(Lead.objects.values_list("status").annotate(n=Count("id")))
    stages = [Lead.NEW, Lead.QUALIFIED, Lead.WON, Lead.LOST]
    return r.chart("bar", [r.series("leads", [(stage, counts.get(stage, 0)) for stage in stages])], fmt="number", label_kind="key", route="/leads")


@r.register_widget("orders_to_fulfill", plugin="sales_crm", kind=r.TABLE, order=610, default_enabled=False)
def orders_to_fulfill(ctx: r.WidgetContext) -> dict:
    orders = sorted(_open_orders(), key=lambda so: (so.expected_date is None, so.expected_date or so.order_date))
    rows = [
        {
            "party": so.party.name,
            "expected_date": str(so.expected_date) if so.expected_date else None,
            "status": so.status,
            "total": str(so.total),
        }
        for so in orders[:8]
    ]
    return r.table(
        [("party", "text"), ("expected_date", "date"), ("status", "status"), ("total", "money")],
        rows,
        route="/sales-orders",
        total_count=len(orders),
    )


@r.register_widget("sales_order_trend", plugin="sales_crm", kind=r.CHART, order=620, default_enabled=False)
def sales_order_trend(ctx: r.WidgetContext) -> dict:
    """Value of sales orders placed per month (drafts and cancellations
    excluded), last six months."""
    starts = month_starts(6)
    orders = (
        SalesOrder.objects.filter(order_date__gte=starts[0])
        .exclude(status__in=[SalesOrder.DRAFT, SalesOrder.CANCELLED])
        .prefetch_related("lines")
    )
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for so in orders:
        totals[month_key(so.order_date)] += so.total
    return r.chart(
        "line", [r.series("order_value", [(month_key(s), totals[month_key(s)]) for s in starts])], label_kind="month", route="/sales-orders"
    )


@r.register_attention("sales_crm")
def _sales_attention(ctx: r.WidgetContext) -> list:
    late = SalesOrder.objects.filter(status__in=OPEN_STATUSES, expected_date__lt=timezone.localdate()).count()
    return [
        r.attention_item("late_sales_orders", late, r.WARNING, "/sales-orders"),
        r.attention_item("new_leads", Lead.objects.filter(status=Lead.NEW).count(), r.INFO, "/leads"),
    ]
