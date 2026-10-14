"""Inventory's home-panel widgets. Registered from InventoryConfig.ready()."""

from decimal import Decimal

from django.db.models import F, Sum

from apps.plugins import registry as r

from .models import StockMove, Warehouse

ZERO = Decimal("0")

# Item has no reorder-point field yet (REQ-INV reorder levels aren't
# modeled), so "low" is one tenant-wide quantity rather than a per-item
# threshold -- revisit when a reorder level exists to compare against.
LOW_STOCK_THRESHOLD = Decimal("5")


def _stock_rows() -> list[dict]:
    """On-hand quantity per item/warehouse pair that has ever had a
    movement -- a single-table Sum() over StockMove, same as
    `services.get_quantity_on_hand`."""
    return list(
        StockMove.objects.values(
            sku=F("item__sku"), item_name=F("item__name"), warehouse_code=F("warehouse__code"), warehouse_name=F("warehouse__name")
        ).annotate(quantity=Sum("quantity"))
    )


def _low_stock_rows() -> list[dict]:
    rows = [row for row in _stock_rows() if row["quantity"] <= LOW_STOCK_THRESHOLD]
    rows.sort(key=lambda row: row["quantity"])
    return rows


@r.register_widget("stock_summary", plugin="inventory", kind=r.STAT, order=180)
def stock_summary(ctx: r.WidgetContext) -> dict:
    in_stock = [row for row in _stock_rows() if row["quantity"] > 0]
    return r.stat(
        len({row["sku"] for row in in_stock}),
        "number",
        secondary=[
            r.secondary("units_on_hand", sum((row["quantity"] for row in in_stock), ZERO)),
            r.secondary("warehouses", Warehouse.objects.filter(is_active=True).count()),
        ],
        route="/stock-levels",
    )


@r.register_widget("low_stock", plugin="inventory", kind=r.TABLE, order=500)
def low_stock(ctx: r.WidgetContext) -> dict:
    low = _low_stock_rows()
    rows = [
        {"sku": row["sku"], "item": row["item_name"], "warehouse": row["warehouse_code"], "quantity": str(row["quantity"])}
        for row in low[:8]
    ]
    return r.table(
        [("sku", "text"), ("item", "text"), ("warehouse", "text"), ("quantity", "number")],
        rows,
        route="/stock-levels",
        total_count=len(low),
    )


@r.register_widget("stock_by_warehouse", plugin="inventory", kind=r.CHART, order=510, default_enabled=False)
def stock_by_warehouse(ctx: r.WidgetContext) -> dict:
    totals: dict[str, Decimal] = {}
    for row in _stock_rows():
        totals[row["warehouse_name"]] = totals.get(row["warehouse_name"], ZERO) + row["quantity"]
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:8]
    return r.chart("hbar", [r.series("units", ranked)], fmt="number", route="/stock-levels")


@r.register_widget("recent_stock_moves", plugin="inventory", kind=r.TABLE, order=520, default_enabled=False)
def recent_stock_moves(ctx: r.WidgetContext) -> dict:
    moves = StockMove.objects.select_related("item", "warehouse").order_by("-created_at")
    rows = [
        {
            "created_at": move.created_at.isoformat(),
            "item": move.item.name,
            "warehouse": move.warehouse.code,
            "move_type": move.move_type,
            "quantity": str(move.quantity),
        }
        for move in moves[:8]
    ]
    return r.table(
        [("created_at", "datetime"), ("item", "text"), ("warehouse", "text"), ("move_type", "status"), ("quantity", "number")],
        rows,
        route="/stock-levels",
        total_count=moves.count(),
    )


@r.register_attention("inventory")
def _inventory_attention(ctx: r.WidgetContext) -> list:
    return [r.attention_item("low_stock", len(_low_stock_rows()), r.WARNING, "/stock-levels")]
