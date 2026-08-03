"""Tests for sales_crm's public service layer (technical.md §4 cross-app
rule) -- apps.ecommerce is the first caller of `create_order()`, so this
exists independent of that package too."""

from decimal import Decimal

from django_tenants.test.cases import TenantTestCase

from apps.core.models import Item, Party
from apps.inventory.models import Warehouse
from apps.sales_crm import services
from apps.sales_crm.models import SalesOrder


class CreateOrderTests(TenantTestCase):
    def setUp(self):
        self.party = Party.objects.create(name="Acme A.Ş.", party_type=Party.CUSTOMER)
        self.warehouse = Warehouse.objects.create(code="WH-A", name="Main")
        self.item = Item.objects.create(sku="ITM-1", name="Widget")

    def test_creates_a_confirmed_order_with_its_lines(self):
        order = services.create_order(
            party=self.party,
            warehouse=self.warehouse,
            order_date="2026-08-01",
            lines=[{"item": self.item, "quantity": Decimal("3"), "unit_price": Decimal("25.00")}],
            memo="Shopify #123",
        )
        self.assertEqual(order.status, SalesOrder.CONFIRMED)
        self.assertEqual(order.memo, "Shopify #123")
        line = order.lines.get()
        self.assertEqual(line.item, self.item)
        self.assertEqual(line.quantity_ordered, Decimal("3"))
        self.assertEqual(line.unit_price, Decimal("25.00"))
