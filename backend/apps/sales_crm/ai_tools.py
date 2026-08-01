"""Sales & CRM's read-only AI metrics (technical.md §8.2/§8.4). Registered
from SalesCrmConfig.ready() -- see apps/sales_crm/apps.py."""

from apps.ai_core.semantic import format_money, register_metric

from .models import Lead, SalesOrder


@register_metric(
    name="open_sales_orders",
    description="Sales orders that are confirmed but not yet fully fulfilled (confirmed or partially_fulfilled status), with customer and total.",
    input_schema={"type": "object", "properties": {}},
    package="sales_crm",
)
def open_sales_orders(**_kwargs) -> dict:
    orders = (
        SalesOrder.objects.filter(status__in=[SalesOrder.CONFIRMED, SalesOrder.PARTIALLY_FULFILLED])
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
                    "customer": o.party.name,
                    "status": o.status,
                    "total": format_money(o.total),
                    "expected_date": str(o.expected_date) if o.expected_date else None,
                }
                for o in orders
            ],
        },
        "citations": [{"label": "Satış Siparişleri / Sales Orders", "route": "/sales-orders"}],
    }


@register_metric(
    name="open_leads",
    description="Leads still in the pipeline (new or qualified status, not yet won or lost).",
    input_schema={"type": "object", "properties": {}},
    package="sales_crm",
)
def open_leads(**_kwargs) -> dict:
    leads = Lead.objects.filter(status__in=[Lead.NEW, Lead.QUALIFIED]).order_by("-created_at")[:10]
    return {
        "result": {
            "count": len(leads),
            "leads": [{"id": l.id, "name": l.name, "status": l.status, "source": l.source} for l in leads],
        },
        "citations": [{"label": "Potansiyel Müşteriler / Leads", "route": "/leads"}],
    }
