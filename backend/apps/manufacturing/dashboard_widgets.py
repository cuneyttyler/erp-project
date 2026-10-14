"""Manufacturing's home-panel widgets. Registered from ManufacturingConfig.ready()."""

from django.db.models import Count
from django.utils import timezone

from apps.plugins import registry as r

from .models import WorkOrder

ACTIVE_STATUSES = [WorkOrder.DRAFT, WorkOrder.RELEASED, WorkOrder.IN_PROGRESS]


@r.register_widget("work_orders_status", plugin="manufacturing", kind=r.CHART, order=650)
def work_orders_status(ctx: r.WidgetContext) -> dict:
    counts = dict(WorkOrder.objects.values_list("status").annotate(n=Count("id")))
    statuses = [WorkOrder.DRAFT, WorkOrder.RELEASED, WorkOrder.IN_PROGRESS, WorkOrder.COMPLETED]
    return r.chart(
        "bar", [r.series("work_orders", [(s, counts.get(s, 0)) for s in statuses])], fmt="number", label_kind="key", route="/work-orders"
    )


@r.register_widget("upcoming_work_orders", plugin="manufacturing", kind=r.TABLE, order=660, default_enabled=False)
def upcoming_work_orders(ctx: r.WidgetContext) -> dict:
    orders = WorkOrder.objects.filter(status__in=ACTIVE_STATUSES).select_related("bom__item").order_by("scheduled_date")
    rows = [
        {
            "item": wo.bom.item.name,
            "scheduled_date": str(wo.scheduled_date),
            "status": wo.status,
            "quantity_completed": str(wo.quantity_completed),
            "quantity_planned": str(wo.quantity_planned),
        }
        for wo in orders[:8]
    ]
    return r.table(
        [("item", "text"), ("scheduled_date", "date"), ("status", "status"), ("quantity_completed", "number"), ("quantity_planned", "number")],
        rows,
        route="/work-orders",
        total_count=orders.count(),
    )


@r.register_attention("manufacturing")
def _manufacturing_attention(ctx: r.WidgetContext) -> list:
    late = WorkOrder.objects.filter(status__in=ACTIVE_STATUSES, scheduled_date__lt=timezone.localdate()).count()
    return [r.attention_item("late_work_orders", late, r.WARNING, "/work-orders")]
