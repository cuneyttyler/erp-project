"""
Public service layer for apps.inventory (technical.md §4 cross-app rule:
packages must not reach into each other's models directly for mutations).
apps.purchasing calls `record_receipt()` when a PO line is received rather
than constructing a StockMove itself -- Inventory owns what a "receipt"
means and how it affects stock, even though the receiving action is
triggered from Purchasing.
"""

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
