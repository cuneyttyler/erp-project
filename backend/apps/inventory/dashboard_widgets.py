"""Inventory's home-panel widgets. Registered from InventoryConfig.ready()."""

import datetime
from collections import defaultdict
from decimal import Decimal

from django.db.models import F, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone

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


# Page charts (see apps/core/dashboard_widgets.py).
@r.register_widget("stock_flow", plugin="inventory", kind=r.CHART, order=1100, default_enabled=False)
def stock_flow(ctx: r.WidgetContext) -> dict:
    """Units received into and shipped out of stock per week, last eight
    weeks. Transfers between warehouses move stock without changing it, so
    they're left out."""
    today = timezone.localdate()
    this_week = today - datetime.timedelta(days=today.weekday())
    weeks = [this_week - datetime.timedelta(weeks=7 - i) for i in range(8)]
    rows = (
        StockMove.objects.filter(created_at__date__gte=weeks[0], move_type__in=[StockMove.RECEIPT, StockMove.PICK])
        .annotate(week=TruncWeek("created_at"))
        .values("week", "move_type")
        .annotate(q=Sum("quantity"))
    )
    totals = defaultdict(lambda: ZERO)
    for row in rows:
        totals[(row["week"].date() if hasattr(row["week"], "date") else row["week"], row["move_type"])] += abs(row["q"] or ZERO)
    return r.chart(
        "bar",
        [
            r.series("received_units", [(week, totals[(week, StockMove.RECEIPT)]) for week in weeks]),
            r.series("shipped_units", [(week, totals[(week, StockMove.PICK)]) for week in weeks]),
        ],
        fmt="number",
        label_kind="date",
        route="/stock-levels",
    )


@r.register_widget("top_stock_items", plugin="inventory", kind=r.CHART, order=1110, default_enabled=False)
def top_stock_items(ctx: r.WidgetContext) -> dict:
    """The items with the most units on hand, across every warehouse."""
    rows = (
        StockMove.objects.values("item__name")
        .annotate(q=Sum("quantity"))
        .filter(q__gt=0)
        .order_by("-q")[:8]
    )
    return r.chart("hbar", [r.series("units", [(row["item__name"], row["q"]) for row in rows])], fmt="number", route="/stock-levels")


@r.register_widget("top_moving_items", plugin="inventory", kind=r.CHART, order=1120, default_enabled=False)
def top_moving_items(ctx: r.WidgetContext) -> dict:
    """The items shipped most in the last 90 days, in units."""
    since = timezone.localdate() - datetime.timedelta(days=89)
    rows = (
        StockMove.objects.filter(move_type=StockMove.PICK, created_at__date__gte=since)
        .values("item__name")
        .annotate(q=Sum("quantity"))
        .order_by("q")[:8]  # picks are negative: the most-shipped sort first
    )
    return r.chart("hbar", [r.series("shipped_units", [(row["item__name"], -row["q"]) for row in rows])], fmt="number", route="/items")
