"""Purchasing's home-panel widgets. Registered from PurchasingConfig.ready()."""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count
from django.utils import timezone

from apps.plugins import registry as r
from apps.plugins.periods import month_key, month_starts

from .models import PurchaseOrder

ZERO = Decimal("0")
OPEN_STATUSES = [PurchaseOrder.SENT, PurchaseOrder.PARTIALLY_RECEIVED]


def _open_orders():
    return PurchaseOrder.objects.filter(status__in=OPEN_STATUSES).select_related("party").prefetch_related("lines")


def _awaiting_approval() -> list[PurchaseOrder]:
    drafts = PurchaseOrder.objects.filter(status=PurchaseOrder.DRAFT, approved_at__isnull=True).prefetch_related("lines")
    return [po for po in drafts if po.requires_approval]


@r.register_widget("open_purchase_orders", plugin="purchasing", kind=r.STAT, order=170)
def open_purchase_orders(ctx: r.WidgetContext) -> dict:
    """Value of everything ordered but not yet fully received."""
    orders = list(_open_orders())
    return r.stat(
        sum((po.total for po in orders), ZERO),
        secondary=[
            r.secondary("open_orders", len(orders)),
            r.secondary("draft_orders", PurchaseOrder.objects.filter(status=PurchaseOrder.DRAFT).count()),
        ],
        route="/purchase-orders",
    )


@r.register_widget("pending_po_receipts", plugin="purchasing", kind=r.TABLE, order=550)
def pending_po_receipts(ctx: r.WidgetContext) -> dict:
    """Open purchase orders by when they're expected -- orders with no
    expected date sort last rather than first."""
    orders = sorted(_open_orders(), key=lambda po: (po.expected_date is None, po.expected_date or po.order_date))
    rows = [
        {
            "party": po.party.name,
            "expected_date": str(po.expected_date) if po.expected_date else None,
            "status": po.status,
            "total": str(po.total),
        }
        for po in orders[:8]
    ]
    return r.table(
        [("party", "text"), ("expected_date", "date"), ("status", "status"), ("total", "money")],
        rows,
        route="/purchase-orders",
        total_count=len(orders),
    )


@r.register_attention("purchasing")
def _purchasing_attention(ctx: r.WidgetContext) -> list:
    late = PurchaseOrder.objects.filter(status__in=OPEN_STATUSES, expected_date__lt=timezone.localdate()).count()
    return [
        r.attention_item("purchase_orders_awaiting_approval", len(_awaiting_approval()), r.WARNING, "/purchase-orders"),
        r.attention_item("late_purchase_orders", late, r.WARNING, "/purchase-orders"),
    ]


# Page charts (see apps/core/dashboard_widgets.py).
@r.register_widget("purchase_trend", plugin="purchasing", kind=r.CHART, order=1200, default_enabled=False)
def purchase_trend(ctx: r.WidgetContext) -> dict:
    """Value of purchase orders placed per month (drafts and cancellations
    excluded), last six months."""
    starts = month_starts(6)
    orders = (
        PurchaseOrder.objects.filter(order_date__gte=starts[0])
        .exclude(status__in=[PurchaseOrder.DRAFT, PurchaseOrder.CANCELLED])
        .prefetch_related("lines")
    )
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for po in orders:
        totals[month_key(po.order_date)] += po.total
    return r.chart("line", [r.series("order_value", [(month_key(s), totals[month_key(s)]) for s in starts])], label_kind="month", route="/purchase-orders")


@r.register_widget("purchase_orders_by_status", plugin="purchasing", kind=r.CHART, order=1210, default_enabled=False)
def purchase_orders_by_status(ctx: r.WidgetContext) -> dict:
    counts = dict(PurchaseOrder.objects.values_list("status").annotate(n=Count("id")))
    statuses = [PurchaseOrder.DRAFT, PurchaseOrder.SENT, PurchaseOrder.PARTIALLY_RECEIVED, PurchaseOrder.RECEIVED]
    return r.chart("bar", [r.series("orders", [(s, counts.get(s, 0)) for s in statuses])], fmt="number", label_kind="key", route="/purchase-orders")
