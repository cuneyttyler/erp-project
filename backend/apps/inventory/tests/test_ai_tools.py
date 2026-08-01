from decimal import Decimal

from django_tenants.test.cases import TenantTestCase

from apps.core.models import Item
from apps.inventory import services
from apps.inventory.ai_tools import stock_on_hand
from apps.inventory.models import Warehouse


class StockOnHandMetricTests(TenantTestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(code="WH-A", name="Main")
        self.item_a = Item.objects.create(sku="AI-1", name="Widget")
        self.item_b = Item.objects.create(sku="AI-2", name="Gadget")
        services.record_receipt(self.item_a, self.warehouse, Decimal("50.00"), "seed")
        services.record_receipt(self.item_b, self.warehouse, Decimal("5.00"), "seed")

    def test_filters_to_requested_sku(self):
        outcome = stock_on_hand(item_sku="AI-1")
        rows = outcome["result"]["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["item_sku"], "AI-1")
        self.assertEqual(rows[0]["quantity_on_hand"], "50.00")

    def test_without_sku_returns_lowest_stock_items_first(self):
        outcome = stock_on_hand()
        rows = outcome["result"]["rows"]
        self.assertEqual(rows[0]["item_sku"], "AI-2")

    def test_zero_net_quantity_is_excluded(self):
        services.record_pick(self.item_b, self.warehouse, Decimal("5.00"), "consumed")
        outcome = stock_on_hand(item_sku="AI-2")
        self.assertEqual(outcome["result"]["rows"], [])
