"""Inventory's read-only AI metrics (technical.md §8.2/§8.4). Registered
from InventoryConfig.ready() -- see apps/inventory/apps.py."""

from django.db.models import F, Sum

from apps.ai_core.semantic import register_metric

from .models import StockMove


@register_metric(
    name="stock_on_hand",
    description=(
        "Current stock-on-hand quantity. Pass `item_sku` to check one item, or omit it to get the "
        "items with the lowest stock across all warehouses."
    ),
    input_schema={
        "type": "object",
        "properties": {"item_sku": {"type": "string", "description": "Exact item SKU, optional."}},
    },
    package="inventory",
)
def stock_on_hand(item_sku: str | None = None, **_kwargs) -> dict:
    queryset = StockMove.objects.values(
        item_sku=F("item__sku"), item_name=F("item__name"), warehouse_code=F("warehouse__code")
    ).annotate(quantity_on_hand=Sum("quantity"))
    if item_sku:
        queryset = queryset.filter(item__sku=item_sku)
    rows = [r for r in queryset if r["quantity_on_hand"] != 0]
    rows.sort(key=lambda r: r["quantity_on_hand"])
    return {
        "result": {
            "rows": [
                {
                    "item_sku": r["item_sku"],
                    "item_name": r["item_name"],
                    "warehouse_code": r["warehouse_code"],
                    "quantity_on_hand": str(r["quantity_on_hand"]),
                }
                for r in rows[:10]
            ]
        },
        "citations": [{"label": "Stok Durumu / Stock Levels", "route": "/stock-levels"}],
    }
