from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import Bill, BillLine, Party
from apps.inventory import services as inventory_services
from apps.inventory.models import Warehouse


class PurchaseOrder(models.Model):
    """
    REQ-PUR-001/002. Status lifecycle: draft -> (approve, if over threshold)
    -> sent -> partially_received/received, or cancelled at any point before
    receiving starts. `warehouse` is the receiving destination for every line
    -- splitting one PO's lines across multiple warehouses is a real need in
    a bigger deployment, but out of scope for this pass (REQ-INV-002 multi-
    warehouse support exists at the Item/StockMove level regardless).

    `APPROVAL_THRESHOLD` is a flat constant, not yet a per-tenant-configurable
    setting -- REQ-CORE-AR-002-equivalent for purchasing
    ("configurable multi-level approval workflows") describes a real feature
    this is a deliberately partial implementation of: one approval gate at
    one fixed threshold, not a configurable multi-level chain. Revisit once
    there's a tenant-settings model to hang a real threshold off of.
    """

    APPROVAL_THRESHOLD = Decimal("10000.00")

    DRAFT = "draft"
    SENT = "sent"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (SENT, "Sent"),
        (PARTIALLY_RECEIVED, "Partially Received"),
        (RECEIVED, "Received"),
        (CANCELLED, "Cancelled"),
    ]

    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name="purchase_orders")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="purchase_orders")
    order_date = models.DateField()
    expected_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    memo = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-order_date", "-id"]

    def __str__(self) -> str:
        return f"PO-{self.id} {self.party.name}"

    @property
    def total(self):
        return sum(
            (line.quantity_ordered * line.unit_price for line in self.lines.all()), Decimal("0")
        )

    @property
    def requires_approval(self):
        return self.total >= self.APPROVAL_THRESHOLD

    def approve(self, user):
        if self.status != self.DRAFT:
            raise ValidationError("Only a draft purchase order can be approved.")
        self.approved_at = timezone.now()
        self.approved_by = user
        self.save(update_fields=["approved_at", "approved_by"])

    def mark_sent(self):
        if self.status != self.DRAFT:
            raise ValidationError("Only a draft purchase order can be sent.")
        if not self.lines.exists():
            raise ValidationError("Cannot send a purchase order with no lines.")
        if self.requires_approval and self.approved_at is None:
            raise ValidationError(
                f"This order totals {self.total} and requires approval "
                f"(threshold {self.APPROVAL_THRESHOLD}) before it can be sent."
            )
        self.status = self.SENT
        self.save(update_fields=["status"])

    @transaction.atomic
    def receive(self, receipt_lines: list[dict]):
        """
        `receipt_lines`: [{"line_id": <PurchaseOrderLine.id>, "quantity": Decimal}, ...]
        For each entry: records a stock receipt via inventory's public
        service (not by touching StockMove directly, per the cross-app rule
        in technical.md §4), advances that line's quantity_received, then
        recomputes the PO's own status. Finally auto-generates one draft AP
        Bill covering everything received in *this* call (REQ-PUR-005's
        three-way-match hint, simplified to PO+receipt driving bill creation
        -- matching against the eventual vendor invoice is a manual step for
        now, not automated three-way matching).
        """
        if self.status not in (self.SENT, self.PARTIALLY_RECEIVED):
            raise ValidationError("Can only receive against a sent purchase order.")

        bill_lines_data = []
        for entry in receipt_lines:
            line = self.lines.select_for_update().get(id=entry["line_id"])
            quantity = Decimal(str(entry["quantity"]))
            remaining = line.quantity_ordered - line.quantity_received
            if quantity <= 0 or quantity > remaining:
                raise ValidationError(
                    f"Line {line.id}: cannot receive {quantity} (remaining {remaining})."
                )
            inventory_services.record_receipt(
                item=line.item, warehouse=self.warehouse, quantity=quantity, reference=f"PO-{self.id}"
            )
            line.quantity_received += quantity
            line.save(update_fields=["quantity_received"])
            bill_lines_data.append((line, quantity))

        # Deliberately NOT `self.lines.all()`: if `self` came from a
        # prefetch_related("lines") queryset (as PurchaseOrderViewSet's does),
        # that accessor returns the *cached* prefetch snapshot taken before
        # this method's own line updates above -- stale quantity_received
        # values, silently misreporting partially_received as fully received
        # or vice versa. A fresh, uncached queryset is required here.
        fresh_lines = PurchaseOrderLine.objects.filter(purchase_order_id=self.id)
        if all(line.quantity_received >= line.quantity_ordered for line in fresh_lines):
            self.status = self.RECEIVED
        else:
            self.status = self.PARTIALLY_RECEIVED
        self.save(update_fields=["status"])

        today = timezone.localdate()
        bill = Bill.objects.create(
            party=self.party,
            issue_date=today,
            due_date=today + timedelta(days=self.party.payment_terms_days),
            memo=f"PO-{self.id} teslim alma",
        )
        for line, quantity in bill_lines_data:
            BillLine.objects.create(
                bill=bill,
                description=f"{line.item.sku} — {line.item.name}",
                quantity=quantity,
                unit_price=line.unit_price,
            )
        return bill


class PurchaseOrderLine(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    # Item is Core master data (apps/core/models.py docstring) -- referenced
    # by string since purchasing depends on core, not the reverse.
    item = models.ForeignKey("core.Item", on_delete=models.PROTECT, related_name="purchase_order_lines")
    quantity_ordered = models.DecimalField(max_digits=14, decimal_places=2)
    quantity_received = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)

    @property
    def amount(self):
        return self.quantity_ordered * self.unit_price

    @property
    def quantity_remaining(self):
        return self.quantity_ordered - self.quantity_received

    def __str__(self) -> str:
        return f"{self.item.sku} x{self.quantity_ordered}"
