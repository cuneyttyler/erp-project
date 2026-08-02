"""POS's read-only AI metrics (technical.md §8.2). Registered from
PosConfig.ready() -- see apps/pos/apps.py."""

from decimal import Decimal

from django.utils import timezone

from apps.ai_core.semantic import format_money, register_metric

from .models import POSSale


@register_metric(
    name="todays_pos_sales",
    description="Total POS sales (net of returns) and transaction count across all stores/tills so far today.",
    input_schema={"type": "object", "properties": {}},
    package="pos",
)
def todays_pos_sales(**_kwargs) -> dict:
    today = timezone.localdate()
    sales = POSSale.objects.filter(created_at__date=today).prefetch_related("lines")
    gross = Decimal("0")
    count = 0
    for sale in sales:
        count += 1
        for line in sale.lines.all():
            gross += line.line_total
    return {
        "result": {"date": str(today), "transaction_count": count, "gross_sales": format_money(gross)},
        "citations": [{"label": "POS Sales", "route": "/pos/sales"}],
    }


@register_metric(
    name="open_pos_shifts",
    description="Currently open POS shifts (till, who opened it, and when) across all stores.",
    input_schema={"type": "object", "properties": {}},
    package="pos",
)
def open_pos_shifts(**_kwargs) -> dict:
    from .models import POSShift

    shifts = POSShift.objects.filter(status=POSShift.OPEN).select_related("till__store", "opened_by")
    return {
        "result": {
            "count": shifts.count(),
            "shifts": [
                {"id": s.id, "till": str(s.till), "opened_by": s.opened_by.username, "opened_at": s.opened_at.isoformat()}
                for s in shifts
            ],
        },
        "citations": [{"label": "POS Shifts", "route": "/pos/shifts"}],
    }
