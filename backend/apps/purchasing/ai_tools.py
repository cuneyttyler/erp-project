"""Purchasing's read-only AI metrics (technical.md §8.2/§8.4). Registered
from PurchasingConfig.ready() -- see apps/purchasing/apps.py."""

from apps.ai_core.semantic import format_money, register_metric

from .models import PurchaseOrder


@register_metric(
    name="open_purchase_orders",
    description="Purchase orders that are sent but not yet fully received (sent or partially_received status), with vendor and total.",
    input_schema={"type": "object", "properties": {}},
    package="purchasing",
)
def open_purchase_orders(**_kwargs) -> dict:
    orders = (
        PurchaseOrder.objects.filter(status__in=[PurchaseOrder.SENT, PurchaseOrder.PARTIALLY_RECEIVED])
        .select_related("party")
        .prefetch_related("lines")
        .order_by("expected_date")[:10]
    )
    return {
        "result": {
            "count": len(orders),
            "orders": [
                {
                    "id": o.id,
                    "vendor": o.party.name,
                    "status": o.status,
                    "total": format_money(o.total),
                    "expected_date": str(o.expected_date) if o.expected_date else None,
                }
                for o in orders
            ],
        },
        "citations": [{"label": "Satın Alma Siparişleri / Purchase Orders", "route": "/purchase-orders"}],
    }
