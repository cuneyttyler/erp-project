"""Manufacturing's read-only AI metrics (technical.md §8.2/§8.4). Registered
from ManufacturingConfig.ready() -- see apps/manufacturing/apps.py."""

from apps.ai_core.semantic import register_metric

from .models import WorkOrder


@register_metric(
    name="pending_work_orders",
    description="Work orders that are released or in progress (not yet completed or cancelled), with planned/completed quantities.",
    input_schema={"type": "object", "properties": {}},
    package="manufacturing",
)
def pending_work_orders(**_kwargs) -> dict:
    orders = (
        WorkOrder.objects.filter(status__in=[WorkOrder.RELEASED, WorkOrder.IN_PROGRESS])
        .select_related("bom__item")
        .order_by("scheduled_date")[:10]
    )
    return {
        "result": {
            "count": len(orders),
            "work_orders": [
                {
                    "id": o.id,
                    "item": o.bom.item.sku,
                    "status": o.status,
                    "quantity_planned": str(o.quantity_planned),
                    "quantity_completed": str(o.quantity_completed),
                    "scheduled_date": str(o.scheduled_date),
                }
                for o in orders
            ],
        },
        "citations": [{"label": "İş Emirleri / Work Orders", "route": "/work-orders"}],
    }
