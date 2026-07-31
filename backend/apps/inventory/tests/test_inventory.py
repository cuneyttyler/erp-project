"""Inventory tests (REQ-INV-001/002/003)."""

from decimal import Decimal

from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import Item, User
from apps.inventory import services
from apps.inventory.models import StockMove, Warehouse


class StockLevelTests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="x")
        self.item = Item.objects.create(sku="ITM-1", name="Widget")
        self.wh_a = Warehouse.objects.create(code="WH-A", name="Main")
        self.wh_b = Warehouse.objects.create(code="WH-B", name="Secondary")

        self.tenant.active_packages = ["inventory"]
        self.tenant.save()

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_receipt_increases_stock_on_hand(self):
        services.record_receipt(self.item, self.wh_a, Decimal("50.00"), "test")
        response = self.client.get(
            "/api/v1/inventory/reports/stock-levels/", HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"50.00"', response.content)
        row = response.data[0]
        # response.data holds the DRF-coerced string ('50.00'), not a Decimal
        # -- that string coercion is the fix this test exists to guard.
        self.assertEqual(row["quantity_on_hand"], "50.00")

    def test_transfer_moves_stock_between_warehouses(self):
        services.record_receipt(self.item, self.wh_a, Decimal("100.00"), "seed")
        response = self.client.post(
            "/api/v1/inventory/stock-moves/transfer/",
            {
                "item": self.item.id,
                "from_warehouse": self.wh_a.id,
                "to_warehouse": self.wh_b.id,
                "quantity": "30.00",
            },
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 200)

        qty_a = sum(m.quantity for m in StockMove.objects.filter(item=self.item, warehouse=self.wh_a))
        qty_b = sum(m.quantity for m in StockMove.objects.filter(item=self.item, warehouse=self.wh_b))
        self.assertEqual(qty_a, Decimal("70.00"))
        self.assertEqual(qty_b, Decimal("30.00"))

    def test_record_receipt_rejects_non_positive_quantity(self):
        with self.assertRaises(ValueError):
            services.record_receipt(self.item, self.wh_a, Decimal("0.00"), "x")

    def test_record_pick_decreases_stock_on_hand(self):
        services.record_receipt(self.item, self.wh_a, Decimal("50.00"), "seed")
        services.record_pick(self.item, self.wh_a, Decimal("20.00"), "so-1")
        self.assertEqual(services.get_quantity_on_hand(self.item, self.wh_a), Decimal("30.00"))

    def test_get_quantity_on_hand_defaults_to_zero(self):
        self.assertEqual(services.get_quantity_on_hand(self.item, self.wh_a), Decimal("0"))

    def test_record_pick_rejects_non_positive_quantity(self):
        with self.assertRaises(ValueError):
            services.record_pick(self.item, self.wh_a, Decimal("0.00"), "x")


class PackageGatingTests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="x")
        self.tenant.active_packages = []  # inventory NOT purchased
        self.tenant.save()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_tenant_without_inventory_package_is_forbidden(self):
        response = self.client.get(
            "/api/v1/inventory/reports/stock-levels/", HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(response.status_code, 403)
