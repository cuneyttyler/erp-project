"""
Public service layer for apps.inventory (technical.md §4 cross-app rule:
packages must not reach into each other's models directly for mutations).
apps.purchasing calls `record_receipt()` when a PO line is received, and
apps.sales_crm calls `record_pick()`/`get_quantity_on_hand()` when a sales
order is fulfilled, rather than either package constructing/querying
StockMove itself -- Inventory owns what stock movements mean, even though
the triggering action lives in a different package.
"""

from decimal import Decimal

from django.db.models import Sum

from .models import StockMove


def record_receipt(item, warehouse, quantity, reference: str) -> StockMove:
    """Records a positive stock receipt. `quantity` must be > 0 -- the
    caller (purchasing.PurchaseOrder.receive()) is responsible for only
    calling this with the quantity actually received."""
    if quantity <= 0:
        raise ValueError("record_receipt requires a positive quantity.")
    return StockMove.objects.create(
        item=item,
        warehouse=warehouse,
        move_type=StockMove.RECEIPT,
        quantity=quantity,
        reference=reference,
    )


def record_pick(item, warehouse, quantity, reference: str) -> StockMove:
    """Records a stock pick (outbound). `quantity` is the positive amount
    being removed -- this function negates it internally; the caller
    (sales_crm.SalesOrder.fulfill()) is responsible for checking availability
    via `get_quantity_on_hand()` first, same division of responsibility as
    `record_receipt()`."""
    if quantity <= 0:
        raise ValueError("record_pick requires a positive quantity.")
    return StockMove.objects.create(
        item=item,
        warehouse=warehouse,
        move_type=StockMove.PICK,
        quantity=-quantity,
        reference=reference,
    )


def get_quantity_on_hand(item, warehouse) -> Decimal:
    """Current stock-on-hand for one item/warehouse pair -- a single-table
    Sum(), safe to compute directly (see StockMove's docstring in models.py)."""
    total = StockMove.objects.filter(item=item, warehouse=warehouse).aggregate(total=Sum("quantity"))[
        "total"
    ]
    return total or Decimal("0")
