from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction

from apps.inventory import services as inventory_services
from apps.inventory.models import Warehouse


class BOM(models.Model):
    """
    Bill of Materials (REQ-MFG-001). Multi-level BOMs are supported
    structurally -- a component_item may itself have its own BOM, modeling a
    sub-assembly -- but WorkOrder.complete() only consumes *this* BOM's
    direct lines; it does not recursively explode a nested sub-assembly's
    BOM down to raw materials. That recursive explosion is a real MRP
    feature (REQ-MFG-003) deferred out of this pass's scope, same as vendor
    price comparison was deferred in Purchasing.
    """

    # Item is Core master data (apps/core/models.py docstring).
    item = models.ForeignKey("core.Item", on_delete=models.PROTECT, related_name="boms")
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["item__sku"]

    def __str__(self) -> str:
        return f"BOM: {self.item.sku} ({self.name})"


class BOMLine(models.Model):
    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name="lines")
    component_item = models.ForeignKey("core.Item", on_delete=models.PROTECT, related_name="+")
    # Quantity of component_item needed to produce ONE unit of the BOM's
    # finished-good item. 4 decimal places (not the usual 2) since
    # per-unit component ratios are often fractional in a way that would
    # lose real precision at 2dp (e.g. 0.0625 kg of an input per unit).
    quantity_per = models.DecimalField(max_digits=14, decimal_places=4)

    def __str__(self) -> str:
        return f"{self.component_item.sku} x{self.quantity_per}"


class WorkOrder(models.Model):
    """
    REQ-MFG-002. Status lifecycle: draft -> released -> in_progress/completed,
    or cancelled before any completion is recorded. Unlike PurchaseOrder/
    SalesOrder, completion tracking is a single `quantity_completed` counter
    on the WorkOrder itself, not per-BOM-line -- a BOM's components are
    consumed as one atomic proportional set per completion run, not
    independently choosable the way PO/SO lines are. That simpler shape also
    means there's no related-manager prefetch-staleness risk to guard against
    here the way there was in Purchasing/Sales & CRM (see those apps'
    receive()/fulfill() comments) -- completion status is computed from two
    scalar fields on `self`, not from re-reading a child collection.
    """

    DRAFT = "draft"
    RELEASED = "released"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (RELEASED, "Released"),
        (IN_PROGRESS, "In Progress"),
        (COMPLETED, "Completed"),
        (CANCELLED, "Cancelled"),
    ]

    bom = models.ForeignKey(BOM, on_delete=models.PROTECT, related_name="work_orders")
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="work_orders"
    )
    quantity_planned = models.DecimalField(max_digits=14, decimal_places=2)
    quantity_completed = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    scheduled_date = models.DateField()
    memo = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scheduled_date", "-id"]

    def __str__(self) -> str:
        return f"WO-{self.id} {self.bom.item.sku}"

    @property
    def quantity_remaining(self):
        return self.quantity_planned - self.quantity_completed

    def release(self):
        if self.status != self.DRAFT:
            raise ValidationError("Only a draft work order can be released.")
        if not self.bom.lines.exists():
            raise ValidationError("Cannot release a work order whose BOM has no components.")
        self.status = self.RELEASED
        self.save(update_fields=["status"])

    @transaction.atomic
    def complete(self, quantity: Decimal):
        """
        Completes (all or part of) this work order: for `quantity` units of
        the BOM's finished good, consumes each component proportionally
        (component.quantity_per * quantity) via inventory's public service
        layer (never touching StockMove directly, per technical.md §4), then
        produces `quantity` units of the finished good into the same
        warehouse. Validates every component has enough stock *before*
        consuming any of them, so a shortage on the last line doesn't leave
        earlier lines partially consumed.
        """
        if self.status not in (self.RELEASED, self.IN_PROGRESS):
            raise ValidationError("Can only complete a released work order.")
        quantity = Decimal(str(quantity))
        if quantity <= 0 or quantity > self.quantity_remaining:
            raise ValidationError(
                f"Cannot complete {quantity} (remaining {self.quantity_remaining})."
            )

        lines = list(self.bom.lines.all())
        shortages = []
        for line in lines:
            needed = line.quantity_per * quantity
            available = inventory_services.get_quantity_on_hand(line.component_item, self.warehouse)
            if needed > available:
                shortages.append(f"{line.component_item.sku} (need {needed}, have {available})")
        if shortages:
            raise ValidationError("Insufficient stock: " + "; ".join(shortages))

        for line in lines:
            needed = line.quantity_per * quantity
            inventory_services.record_pick(
                item=line.component_item,
                warehouse=self.warehouse,
                quantity=needed,
                reference=f"WO-{self.id}",
            )

        inventory_services.record_receipt(
            item=self.bom.item, warehouse=self.warehouse, quantity=quantity, reference=f"WO-{self.id}"
        )

        self.quantity_completed += quantity
        self.status = self.COMPLETED if self.quantity_remaining <= 0 else self.IN_PROGRESS
        self.save(update_fields=["quantity_completed", "status"])
