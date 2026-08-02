"""
Point of Sale (REQ-POS-001/002/004/005/006, development-plan.md §6 Phase 3).

Scope cuts, documented once here rather than repeated per model:
- Fiscal payment device integration and e-Arşiv receipt generation
  (REQ-POS-003/007, REQ-LOC-TR-011) are NOT built -- they depend on the same
  GİB-connectivity decision (build-vs-partner) that's blocked every other
  Turkey compliance filing on since Phase 1 (docs/notes.md #1). A `POSSale`
  is a real, GL-posted transaction; what's missing is the statutory fiscal
  receipt/e-Arşiv document generated *from* it, not the sale itself.
- No per-line VAT/tax-rate breakdown -- `unit_price` is a flat line amount,
  the same simplification `InvoiceLine`/`BillLine` already make elsewhere in
  this codebase (neither models a tax rate either). A real Z-report under
  Turkish fiscal rules needs a statutory per-rate VAT breakdown; what's built
  here is the cash/sales reconciliation half of "Z-report" (REQ-POS-004),
  not the fiscal-device-certified document.
- REQ-POS-006 ("loyalty/discount program configuration") is scoped to a
  manual discount amount per sale line at checkout -- a persistent,
  customer-linked points-accrual loyalty program is real follow-up work, not
  hidden behind this existing.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.ai_core.semantic import format_money
from apps.core.models import Entity, JournalEntry
from apps.inventory.models import Warehouse


class Store(models.Model):
    """A physical retail location (REQ-POS-002). Each store belongs to one
    legal entity's books and draws stock from one Inventory warehouse --
    multi-store reporting into "central Inventory and GL" falls out of that
    directly, the same way multi-entity GL already works (Account/
    JournalEntry/Party's `entity` FK)."""

    entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="pos_stores")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="pos_stores")
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class Till(models.Model):
    """A single register/terminal within a store (REQ-POS-002)."""

    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="tills")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["store__code", "code"]
        constraints = [models.UniqueConstraint(fields=["store", "code"], name="unique_till_code_per_store")]

    def __str__(self) -> str:
        return f"{self.store.code}/{self.code} — {self.name}"


class POSShift(models.Model):
    """
    One open-to-close working session on a till. Every `POSSale` belongs to
    exactly one shift -- the shift is what a Z-report (REQ-POS-004)
    reconciles, not the till in the abstract (a till has many shifts over
    its lifetime).
    """

    OPEN = "open"
    CLOSED = "closed"
    STATUS_CHOICES = [(OPEN, "Open"), (CLOSED, "Closed")]

    till = models.ForeignKey(Till, on_delete=models.PROTECT, related_name="shifts")
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    opening_cash = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    closing_cash_counted = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self) -> str:
        return f"Shift #{self.id} ({self.till})"

    def close(self, closing_cash_counted):
        if self.status != self.OPEN:
            raise ValidationError("Only an open shift can be closed.")
        self.closing_cash_counted = closing_cash_counted
        self.status = self.CLOSED
        self.closed_at = timezone.now()
        self.save(update_fields=["closing_cash_counted", "status", "closed_at"])

    def z_report(self) -> dict:
        """
        REQ-POS-004: the sales/cash reconciliation half of a Z-report (see
        this module's docstring for what's deliberately not built -- the
        statutory fiscal-device Z-rapor format). Callable at any time, not
        just after `close()`, so a till operator can preview it before
        actually closing.
        """
        gross_sales = Decimal("0")
        by_method: dict[str, Decimal] = {}
        sales = self.sales.prefetch_related("lines", "payments")
        for sale in sales:
            for line in sale.lines.all():
                gross_sales += line.line_total
            for payment in sale.payments.all():
                by_method[payment.method] = by_method.get(payment.method, Decimal("0")) + payment.amount

        returns_total = Decimal("0")
        refunds_by_method: dict[str, Decimal] = {}
        for pos_return in POSReturn.objects.filter(sale__shift=self).prefetch_related("lines"):
            for line in pos_return.lines.all():
                returns_total += line.refund_amount
                refunds_by_method[pos_return.refund_method] = (
                    refunds_by_method.get(pos_return.refund_method, Decimal("0")) + line.refund_amount
                )

        net_by_method = {
            method: by_method.get(method, Decimal("0")) - refunds_by_method.get(method, Decimal("0"))
            for method in set(by_method) | set(refunds_by_method)
        }
        cash_net = net_by_method.get(POSPayment.CASH, Decimal("0"))
        expected_cash = self.opening_cash + cash_net
        discrepancy = (self.closing_cash_counted - expected_cash) if self.closing_cash_counted is not None else None

        return {
            "shift_id": self.id,
            "till": str(self.till),
            "status": self.status,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "transaction_count": sales.count(),
            "gross_sales": format_money(gross_sales),
            "returns_total": format_money(returns_total),
            "net_sales": format_money(gross_sales - returns_total),
            "by_payment_method": {k: format_money(v) for k, v in net_by_method.items()},
            "opening_cash": format_money(self.opening_cash),
            "expected_cash": format_money(expected_cash),
            "closing_cash_counted": format_money(self.closing_cash_counted) if self.closing_cash_counted is not None else None,
            "cash_discrepancy": format_money(discrepancy) if discrepancy is not None else None,
        }


class POSSale(models.Model):
    """
    A completed register sale (REQ-POS-001). Unlike Invoice/SalesOrder there
    is no draft state -- a POS sale settles immediately at checkout
    (`apps.pos.services.checkout()`), which is also what posts stock moves
    and the GL entry atomically; this row and its lines only exist once that
    whole transaction has already succeeded.
    """

    COMPLETED = "completed"
    PARTIALLY_RETURNED = "partially_returned"
    RETURNED = "returned"
    STATUS_CHOICES = [
        (COMPLETED, "Completed"),
        (PARTIALLY_RETURNED, "Partially Returned"),
        (RETURNED, "Returned"),
    ]

    shift = models.ForeignKey(POSShift, on_delete=models.PROTECT, related_name="sales")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=COMPLETED)
    # A client-generated idempotency key (REQ-POS-008): the offline queue
    # replays a queued sale once connectivity returns, and may retry a
    # submission whose response it never saw -- `checkout()` treats a repeat
    # of the same client_reference as "already happened," not a new sale.
    client_reference = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    journal_entry = models.OneToOneField(
        JournalEntry, null=True, on_delete=models.SET_NULL, related_name="pos_sale"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"POS-{self.id}"

    @property
    def subtotal(self):
        return sum((line.line_total for line in self.lines.all()), Decimal("0"))

    @property
    def total_paid(self):
        return sum((p.amount for p in self.payments.all()), Decimal("0"))


class POSSaleLine(models.Model):
    sale = models.ForeignKey(POSSale, on_delete=models.CASCADE, related_name="lines")
    # Item is Core master data (apps/core/models.py's Item docstring).
    item = models.ForeignKey("core.Item", on_delete=models.PROTECT, related_name="pos_sale_lines")
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    quantity_returned = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def __str__(self) -> str:
        return f"{self.item.sku} x{self.quantity}"

    @property
    def line_total(self):
        return (self.quantity * self.unit_price) - self.discount_amount

    @property
    def net_unit_price(self):
        """Line total spread evenly per unit -- what a partial return refunds
        per unit returned, so a discounted line's discount is proportionally
        honored on a partial return rather than refunding the pre-discount price."""
        if self.quantity == 0:
            return Decimal("0")
        return self.line_total / self.quantity


class POSPayment(models.Model):
    CASH = "cash"
    CARD = "card"
    METHOD_CHOICES = [(CASH, "Cash"), (CARD, "Card")]

    sale = models.ForeignKey(POSSale, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.method} {self.amount}"


class POSReturn(models.Model):
    """A return/exchange against a completed sale (REQ-POS-005). Always
    refers back to the original sale rather than standing alone -- a return
    with no sale to return against isn't a supported flow here (that's a
    stock adjustment, a different existing feature in Inventory)."""

    sale = models.ForeignKey(POSSale, on_delete=models.PROTECT, related_name="returns")
    refund_method = models.CharField(max_length=10, choices=POSPayment.METHOD_CHOICES)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    reason = models.CharField(max_length=255, blank=True)
    journal_entry = models.OneToOneField(
        JournalEntry, null=True, on_delete=models.SET_NULL, related_name="pos_return"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Return #{self.id} (sale {self.sale_id})"

    @property
    def lines_refund_total(self):
        return sum((line.refund_amount for line in self.lines.all()), Decimal("0"))


class POSReturnLine(models.Model):
    pos_return = models.ForeignKey(POSReturn, on_delete=models.CASCADE, related_name="lines")
    sale_line = models.ForeignKey(POSSaleLine, on_delete=models.PROTECT, related_name="return_lines")
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    refund_amount = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.sale_line.item.sku} x{self.quantity} return"
