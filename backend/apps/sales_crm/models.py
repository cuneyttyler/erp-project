from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import Invoice, InvoiceLine, Party
from apps.inventory import services as inventory_services
from apps.inventory.models import Warehouse


class Lead(models.Model):
    """
    Lead/opportunity pipeline (REQ-CRM-001). Deliberately a single flat
    status field rather than a configurable multi-stage pipeline -- a real
    "configurable pipeline" feature (custom stages per tenant) is a bigger
    piece of work than this pass's scope; new/qualified/won/lost covers the
    minimum viable version of "track a lead through to close."
    """

    NEW = "new"
    QUALIFIED = "qualified"
    WON = "won"
    LOST = "lost"
    STATUS_CHOICES = [(NEW, "New"), (QUALIFIED, "Qualified"), (WON, "Won"), (LOST, "Lost")]

    name = models.CharField(max_length=255)
    party = models.ForeignKey(
        Party, null=True, blank=True, on_delete=models.SET_NULL, related_name="leads"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=NEW)
    source = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    def qualify(self):
        if self.status != self.NEW:
            raise ValidationError("Only a new lead can be qualified.")
        self.status = self.QUALIFIED
        self.save(update_fields=["status"])

    def mark_won(self, party: Party):
        if self.status not in (self.NEW, self.QUALIFIED):
            raise ValidationError("Only an open lead can be marked won.")
        self.status = self.WON
        self.party = party
        self.save(update_fields=["status", "party"])

    def mark_lost(self):
        if self.status in (self.WON, self.LOST):
            raise ValidationError("Lead is already closed.")
        self.status = self.LOST
        self.save(update_fields=["status"])


class SalesOrder(models.Model):
    """
    REQ-CRM-002/003. Status lifecycle: draft (working quote) -> confirmed
    (customer accepted) -> partially_fulfilled/fulfilled, or cancelled before
    fulfillment starts. Unlike PurchaseOrder there is no approval-threshold
    gate here -- REQ-CRM doesn't call for one, and inventing an approval
    workflow purchasing-requirements never asked for on the sales side would
    be scope creep in the other direction.
    """

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PARTIALLY_FULFILLED = "partially_fulfilled"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (CONFIRMED, "Confirmed"),
        (PARTIALLY_FULFILLED, "Partially Fulfilled"),
        (FULFILLED, "Fulfilled"),
        (CANCELLED, "Cancelled"),
    ]

    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name="sales_orders")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="sales_orders")
    order_date = models.DateField()
    expected_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    memo = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-order_date", "-id"]

    def __str__(self) -> str:
        return f"SO-{self.id} {self.party.name}"

    @property
    def total(self):
        return sum(
            (line.quantity_ordered * line.unit_price for line in self.lines.all()), Decimal("0")
        )

    def confirm(self):
        if self.status != self.DRAFT:
            raise ValidationError("Only a draft sales order can be confirmed.")
        if not self.lines.exists():
            raise ValidationError("Cannot confirm a sales order with no lines.")
        self.status = self.CONFIRMED
        self.save(update_fields=["status"])

    @transaction.atomic
    def fulfill(self, fulfillment_lines: list[dict]):
        """
        `fulfillment_lines`: [{"line_id": <SalesOrderLine.id>, "quantity": Decimal}, ...]
        Mirrors PurchaseOrder.receive(): validates remaining quantity AND
        available stock, picks via inventory's public service (never
        touching StockMove directly -- technical.md §4), advances
        quantity_fulfilled, recomputes status from a *fresh* queryset (not
        `self.lines.all()` -- see purchasing.models.PurchaseOrder.receive()'s
        comment for the prefetch-staleness bug this avoids repeating), then
        auto-generates a draft AR Invoice for what was just shipped.
        """
        if self.status not in (self.CONFIRMED, self.PARTIALLY_FULFILLED):
            raise ValidationError("Can only fulfill a confirmed sales order.")

        invoice_lines_data = []
        for entry in fulfillment_lines:
            line = self.lines.select_for_update().get(id=entry["line_id"])
            quantity = Decimal(str(entry["quantity"]))
            remaining = line.quantity_ordered - line.quantity_fulfilled
            if quantity <= 0 or quantity > remaining:
                raise ValidationError(
                    f"Line {line.id}: cannot fulfill {quantity} (remaining {remaining})."
                )
            available = inventory_services.get_quantity_on_hand(line.item, self.warehouse)
            if quantity > available:
                raise ValidationError(
                    f"Line {line.id}: only {available} of {line.item.sku} in stock at "
                    f"{self.warehouse.code}, cannot ship {quantity}."
                )
            inventory_services.record_pick(
                item=line.item, warehouse=self.warehouse, quantity=quantity, reference=f"SO-{self.id}"
            )
            line.quantity_fulfilled += quantity
            line.save(update_fields=["quantity_fulfilled"])
            invoice_lines_data.append((line, quantity))

        fresh_lines = SalesOrderLine.objects.filter(sales_order_id=self.id)
        if all(line.quantity_fulfilled >= line.quantity_ordered for line in fresh_lines):
            self.status = self.FULFILLED
        else:
            self.status = self.PARTIALLY_FULFILLED
        self.save(update_fields=["status"])

        today = timezone.localdate()
        invoice = Invoice.objects.create(
            party=self.party,
            issue_date=today,
            due_date=today + timedelta(days=self.party.payment_terms_days),
            memo=f"SO-{self.id} sevkiyat",
        )
        for line, quantity in invoice_lines_data:
            InvoiceLine.objects.create(
                invoice=invoice,
                description=f"{line.item.sku} — {line.item.name}",
                quantity=quantity,
                unit_price=line.unit_price,
            )
        return invoice


class SalesOrderLine(models.Model):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="lines")
    # Item is Core master data (apps/core/models.py docstring).
    item = models.ForeignKey("core.Item", on_delete=models.PROTECT, related_name="sales_order_lines")
    quantity_ordered = models.DecimalField(max_digits=14, decimal_places=2)
    quantity_fulfilled = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)

    @property
    def amount(self):
        return self.quantity_ordered * self.unit_price

    @property
    def quantity_remaining(self):
        return self.quantity_ordered - self.quantity_fulfilled

    def __str__(self) -> str:
        return f"{self.item.sku} x{self.quantity_ordered}"
