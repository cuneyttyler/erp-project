from django.db import models


class Warehouse(models.Model):
    """A physical or logical stock location (REQ-INV-002)."""

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class StockMove(models.Model):
    """
    A single signed stock movement (REQ-INV-002/003). Quantity-on-hand for an
    item/warehouse is `Sum(quantity)` over this table -- safe to compute via a
    SQL aggregate (unlike FinancialDocument's total/balance) since this is a
    single flat table with no second relation to join against and fan out.
    A transfer between warehouses is modeled as two paired rows (a negative
    OUT at the source, a positive IN at the destination) created atomically
    by `transfer_stock()` in views.py, rather than a single row with two
    warehouse FKs -- keeps "sum of quantity per warehouse" meaningful without
    special-casing transfer rows in every report query.
    """

    RECEIPT = "receipt"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    ADJUSTMENT = "adjustment"
    PICK = "pick"
    MOVE_TYPE_CHOICES = [
        (RECEIPT, "Receipt"),
        (TRANSFER_IN, "Transfer In"),
        (TRANSFER_OUT, "Transfer Out"),
        (ADJUSTMENT, "Adjustment"),
        (PICK, "Pick"),
    ]

    # Item is Core master data (technical.md §5: "shared by Inventory,
    # Purchasing, Sales, Manufacturing"), not an Inventory-owned model --
    # referenced by string to avoid a hard import from a package into core's
    # module (core itself has no reverse dependency on inventory).
    item = models.ForeignKey("core.Item", on_delete=models.PROTECT, related_name="stock_moves")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_moves")
    move_type = models.CharField(max_length=20, choices=MOVE_TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.item.sku} {self.quantity:+} @ {self.warehouse.code} ({self.move_type})"
