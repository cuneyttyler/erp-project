"""Purchasing's home-panel widgets. Registered from PurchasingConfig.ready()."""

from decimal import Decimal

from django.utils import timezone

from apps.plugins import registry as r

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
