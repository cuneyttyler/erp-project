"""
Checkout/return orchestration (REQ-POS-001/005). Kept as a services module,
not model methods, since a checkout touches three concerns at once -- Item
pricing/lines, Inventory stock deduction via its own public service layer
(technical.md §4 cross-app rule), and GL posting -- the same shape as
`sales_crm.SalesOrder.fulfill()`, just without an intermediate draft state
since a POS sale settles immediately at the register.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.models import Account, Item, JournalEntry, JournalLine
from apps.inventory import services as inventory_services

from .models import POSPayment, POSReturn, POSReturnLine, POSSale, POSSaleLine, POSShift

# Tekdüzen Hesap Planı codes (seed_chart_of_accounts.py) -- same
# Turkey-specific-today caveat as core/ai_tools.py's CASH_ACCOUNT_CODES.
PAYMENT_ACCOUNT_CODES = {POSPayment.CASH: "100", POSPayment.CARD: "102"}
REVENUE_ACCOUNT_CODE = "600"
RETURNS_ACCOUNT_CODE = "610"


def _get_account(entity, code):
    try:
        return Account.objects.get(entity=entity, code=code)
    except Account.DoesNotExist as exc:
        raise ValidationError(
            f"Entity '{entity.code}' is missing Chart of Accounts entry {code} -- seed it before taking POS sales."
        ) from exc


@transaction.atomic
def checkout(shift: POSShift, lines: list[dict], payments: list[dict], user, client_reference: str = "") -> POSSale:
    """
    `lines`: [{"item_id": int, "quantity": Decimal, "unit_price": Decimal, "discount_amount": Decimal}, ...]
    `payments`: [{"method": "cash"|"card", "amount": Decimal}, ...]
    """
    if shift.status != POSShift.OPEN:
        raise ValidationError("Cannot take a sale on a closed shift.")
    if not lines:
        raise ValidationError("A sale needs at least one line.")
    if not payments:
        raise ValidationError("A sale needs at least one payment.")

    if client_reference:
        existing = POSSale.objects.filter(client_reference=client_reference).first()
        if existing is not None:
            # Idempotent replay of an offline-queued retry (REQ-POS-008) --
            # the client can't tell whether its earlier submission actually
            # landed before the connection dropped, so a repeat is treated
            # as "already happened," not a second sale.
            return existing

    store = shift.till.store
    sale = POSSale.objects.create(shift=shift, created_by=user, client_reference=client_reference or None)

    subtotal = Decimal("0")
    for entry in lines:
        item = Item.objects.get(id=entry["item_id"])
        quantity = Decimal(str(entry["quantity"]))
        unit_price = Decimal(str(entry["unit_price"]))
        discount = Decimal(str(entry.get("discount_amount", "0")))
        if quantity <= 0:
            raise ValidationError(f"Line quantity for {item.sku} must be positive.")
        available = inventory_services.get_quantity_on_hand(item, store.warehouse)
        if quantity > available:
            raise ValidationError(f"Only {available} of {item.sku} in stock at {store.code}.")
        POSSaleLine.objects.create(
            sale=sale, item=item, quantity=quantity, unit_price=unit_price, discount_amount=discount
        )
        inventory_services.record_pick(item=item, warehouse=store.warehouse, quantity=quantity, reference=f"POS-{sale.id}")
        subtotal += quantity * unit_price - discount

    total_paid = Decimal("0")
    for entry in payments:
        amount = Decimal(str(entry["amount"]))
        if amount <= 0:
            raise ValidationError("Payment amounts must be positive.")
        POSPayment.objects.create(sale=sale, method=entry["method"], amount=amount)
        total_paid += amount

    if total_paid != subtotal:
        raise ValidationError(f"Payments ({total_paid}) do not cover the sale total ({subtotal}).")

    entity = store.entity
    entry_gl = JournalEntry.objects.create(
        entity=entity, date=timezone.localdate(), memo=f"POS sale #{sale.id} ({shift.till})", status=JournalEntry.DRAFT
    )
    for payment in sale.payments.all():
        JournalLine.objects.create(
            journal_entry=entry_gl,
            account=_get_account(entity, PAYMENT_ACCOUNT_CODES[payment.method]),
            debit=payment.amount,
            credit=0,
            description=f"POS {payment.method}",
        )
    JournalLine.objects.create(
        journal_entry=entry_gl,
        account=_get_account(entity, REVENUE_ACCOUNT_CODE),
        debit=0,
        credit=subtotal,
        description=f"POS sale #{sale.id}",
    )
    entry_gl.post()

    sale.journal_entry = entry_gl
    sale.save(update_fields=["journal_entry"])
    return sale


@transaction.atomic
def return_sale(sale: POSSale, lines: list[dict], user, refund_method: str, reason: str = "") -> POSReturn:
    """`lines`: [{"sale_line_id": int, "quantity": Decimal}, ...] -- quantities
    being returned, checked against what's left un-returned on each line."""
    if sale.status not in (POSSale.COMPLETED, POSSale.PARTIALLY_RETURNED):
        raise ValidationError("Only a completed (or partially returned) sale can be returned against.")
    if not lines:
        raise ValidationError("A return needs at least one line.")

    store = sale.shift.till.store
    pos_return = POSReturn.objects.create(sale=sale, created_by=user, refund_method=refund_method, reason=reason)

    refund_total = Decimal("0")
    for entry in lines:
        line = sale.lines.select_for_update().get(id=entry["sale_line_id"])
        quantity = Decimal(str(entry["quantity"]))
        remaining = line.quantity - line.quantity_returned
        if quantity <= 0 or quantity > remaining:
            raise ValidationError(f"Line {line.id}: cannot return {quantity} (remaining {remaining}).")
        refund_amount = (line.net_unit_price * quantity).quantize(Decimal("0.01"))
        POSReturnLine.objects.create(pos_return=pos_return, sale_line=line, quantity=quantity, refund_amount=refund_amount)
        inventory_services.record_receipt(
            item=line.item, warehouse=store.warehouse, quantity=quantity, reference=f"POS-RETURN-{pos_return.id}"
        )
        line.quantity_returned += quantity
        line.save(update_fields=["quantity_returned"])
        refund_total += refund_amount

    fresh_lines = list(POSSaleLine.objects.filter(sale_id=sale.id))
    sale.status = POSSale.RETURNED if all(l.quantity_returned >= l.quantity for l in fresh_lines) else POSSale.PARTIALLY_RETURNED
    sale.save(update_fields=["status"])

    entity = store.entity
    entry_gl = JournalEntry.objects.create(
        entity=entity, date=timezone.localdate(), memo=f"POS return #{pos_return.id} (sale #{sale.id})", status=JournalEntry.DRAFT
    )
    JournalLine.objects.create(
        journal_entry=entry_gl,
        account=_get_account(entity, RETURNS_ACCOUNT_CODE),
        debit=refund_total,
        credit=0,
        description="POS return",
    )
    JournalLine.objects.create(
        journal_entry=entry_gl,
        account=_get_account(entity, PAYMENT_ACCOUNT_CODES[refund_method]),
        debit=0,
        credit=refund_total,
        description=f"POS refund ({refund_method})",
    )
    entry_gl.post()

    pos_return.journal_entry = entry_gl
    pos_return.save(update_fields=["journal_entry"])
    return pos_return
