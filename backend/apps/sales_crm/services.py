"""Public service layer for apps.sales_crm (technical.md §4 cross-app rule).
apps.ecommerce calls `create_order()` when an external marketplace order
syncs in, rather than constructing SalesOrder/SalesOrderLine directly --
same "cross-package interactions go through a public service layer, never
another app's models directly" discipline as apps.inventory.services."""

from django.db import transaction

from .models import SalesOrder, SalesOrderLine


@transaction.atomic
def create_order(party, warehouse, order_date, lines: list[dict], memo: str = "") -> SalesOrder:
    """`lines`: [{"item": Item, "quantity": Decimal, "unit_price": Decimal}, ...].
    Returns a CONFIRMED order -- an externally-sourced order (e.g. a
    marketplace sale) already represents a customer commitment, not a draft
    quote a salesperson is still drafting. Fulfillment (stock deduction,
    the AR invoice) still only happens through the existing explicit
    `SalesOrder.fulfill()` call, same as any other sales order."""
    order = SalesOrder.objects.create(party=party, warehouse=warehouse, order_date=order_date, memo=memo)
    for line in lines:
        SalesOrderLine.objects.create(
            sales_order=order, item=line["item"], quantity_ordered=line["quantity"], unit_price=line["unit_price"]
        )
    order.confirm()
    return order
