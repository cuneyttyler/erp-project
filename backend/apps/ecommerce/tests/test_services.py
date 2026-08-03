"""Correctness tests for sync/stock-push orchestration (REQ-ECOM-001/003).
Mocks the adapter layer (adapters.get_adapter) so these never touch
`requests` -- what matters here is the ERP-side logic: dedup by
external_order_id, creating a real SalesOrder, and failing (not silently
skipping) an order whose SKU has no listing mapping."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django_tenants.test.cases import TenantTestCase

from apps.core.models import Entity, Item, Party
from apps.ecommerce import services
from apps.ecommerce.adapters import ExternalOrder, ExternalOrderLine
from apps.ecommerce.models import MarketplaceAccount, MarketplaceListing, MarketplaceOrder
from apps.inventory import services as inventory_services
from apps.inventory.models import Warehouse
from apps.sales_crm.models import SalesOrder


class SyncOrdersTestBase(TenantTestCase):
    def setUp(self):
        self.entity = Entity.objects.create(name="Acme A.Ş.", code="ACME")
        self.warehouse = Warehouse.objects.create(code="ECOM-DEPO", name="E-ticaret Depo")
        self.account = MarketplaceAccount.objects.create(
            platform=MarketplaceAccount.SHOPIFY,
            name="My Shopify Store",
            entity=self.entity,
            warehouse=self.warehouse,
            shop_domain="test-shop.myshopify.com",
            api_secret="shpat_test",
        )
        self.item = Item.objects.create(sku="ITEM-1", name="Widget")
        inventory_services.record_receipt(item=self.item, warehouse=self.warehouse, quantity=Decimal("100"), reference="seed")
        self.listing = MarketplaceListing.objects.create(
            account=self.account, item=self.item, external_sku="SHOPIFY-SKU-1", external_variant_id="1", external_location_id="1"
        )

    def _mock_orders(self, orders):
        return patch("apps.ecommerce.services.adapters.get_adapter", return_value=MagicMock(fetch_new_orders=MagicMock(return_value=orders)))


class SyncOrdersTests(SyncOrdersTestBase):
    def test_creates_a_confirmed_sales_order_for_a_new_external_order(self):
        ext_order = ExternalOrder(
            external_order_id="1001",
            customer_email="buyer@example.com",
            customer_name="Ayşe Yılmaz",
            lines=[ExternalOrderLine(sku="SHOPIFY-SKU-1", quantity=Decimal("2"), unit_price=Decimal("49.90"))],
        )
        with self._mock_orders([ext_order]):
            result = services.sync_orders(self.account)

        self.assertEqual(result, {"created": 1, "skipped": 0, "failed": 0})
        marketplace_order = MarketplaceOrder.objects.get(external_order_id="1001")
        self.assertEqual(marketplace_order.status, MarketplaceOrder.SYNCED)
        self.assertIsNotNone(marketplace_order.sales_order)
        self.assertEqual(marketplace_order.sales_order.status, SalesOrder.CONFIRMED)
        self.assertEqual(marketplace_order.sales_order.lines.get().item, self.item)

    def test_reuses_the_party_for_a_repeat_customer_email(self):
        ext_order_1 = ExternalOrder("1001", "buyer@example.com", "Ayşe Yılmaz", [ExternalOrderLine("SHOPIFY-SKU-1", Decimal("1"), Decimal("10.00"))])
        ext_order_2 = ExternalOrder("1002", "buyer@example.com", "Ayşe Yılmaz", [ExternalOrderLine("SHOPIFY-SKU-1", Decimal("1"), Decimal("10.00"))])
        with self._mock_orders([ext_order_1]):
            services.sync_orders(self.account)
        with self._mock_orders([ext_order_2]):
            services.sync_orders(self.account)

        self.assertEqual(Party.objects.filter(email="buyer@example.com").count(), 1)

    def test_guest_orders_with_no_email_share_one_bucket_party(self):
        ext_order_1 = ExternalOrder("1001", "", "", [ExternalOrderLine("SHOPIFY-SKU-1", Decimal("1"), Decimal("10.00"))])
        ext_order_2 = ExternalOrder("1002", "", "", [ExternalOrderLine("SHOPIFY-SKU-1", Decimal("1"), Decimal("10.00"))])
        with self._mock_orders([ext_order_1, ext_order_2]):
            services.sync_orders(self.account)

        self.assertEqual(Party.objects.filter(name="E-ticaret Misafir Müşteri").count(), 1)

    def test_reprocessing_the_same_external_order_id_is_a_no_op(self):
        ext_order = ExternalOrder("1001", "buyer@example.com", "Ayşe", [ExternalOrderLine("SHOPIFY-SKU-1", Decimal("1"), Decimal("10.00"))])
        with self._mock_orders([ext_order]):
            services.sync_orders(self.account)
        with self._mock_orders([ext_order]):
            result = services.sync_orders(self.account)

        self.assertEqual(result, {"created": 0, "skipped": 1, "failed": 0})
        self.assertEqual(MarketplaceOrder.objects.filter(external_order_id="1001").count(), 1)
        self.assertEqual(SalesOrder.objects.count(), 1)

    def test_order_with_unmapped_sku_is_marked_failed_not_silently_dropped(self):
        ext_order = ExternalOrder("1001", "buyer@example.com", "Ayşe", [ExternalOrderLine("UNKNOWN-SKU", Decimal("1"), Decimal("10.00"))])
        with self._mock_orders([ext_order]):
            result = services.sync_orders(self.account)

        self.assertEqual(result, {"created": 0, "skipped": 0, "failed": 1})
        marketplace_order = MarketplaceOrder.objects.get(external_order_id="1001")
        self.assertEqual(marketplace_order.status, MarketplaceOrder.FAILED)
        self.assertTrue(marketplace_order.error)
        self.assertIsNone(marketplace_order.sales_order)

    def test_sync_updates_last_synced_at(self):
        self.assertIsNone(self.account.last_synced_at)
        with self._mock_orders([]):
            services.sync_orders(self.account)
        self.account.refresh_from_db()
        self.assertIsNotNone(self.account.last_synced_at)

    def test_cannot_sync_a_deactivated_account(self):
        self.account.is_active = False
        self.account.save()
        with self.assertRaises(ValidationError):
            services.sync_orders(self.account)


class PushStockLevelsTests(SyncOrdersTestBase):
    def test_pushes_current_on_hand_quantity_for_each_active_listing(self):
        mock_adapter = MagicMock()
        with patch("apps.ecommerce.services.adapters.get_adapter", return_value=mock_adapter):
            result = services.push_stock_levels(self.account)

        self.assertEqual(result, {"pushed": 1, "failed": 0})
        mock_adapter.push_stock_level.assert_called_once()
        call_args = mock_adapter.push_stock_level.call_args
        self.assertEqual(call_args.args[0], self.listing)
        self.assertEqual(call_args.args[1], Decimal("100"))

    def test_a_failing_listing_push_is_counted_not_raised(self):
        mock_adapter = MagicMock()
        mock_adapter.push_stock_level.side_effect = Exception("network blew up")
        with patch("apps.ecommerce.services.adapters.get_adapter", return_value=mock_adapter):
            result = services.push_stock_levels(self.account)
        self.assertEqual(result, {"pushed": 0, "failed": 1})

    def test_inactive_listings_are_not_pushed(self):
        self.listing.is_active = False
        self.listing.save()
        mock_adapter = MagicMock()
        with patch("apps.ecommerce.services.adapters.get_adapter", return_value=mock_adapter):
            result = services.push_stock_levels(self.account)
        self.assertEqual(result, {"pushed": 0, "failed": 0})
        mock_adapter.push_stock_level.assert_not_called()
