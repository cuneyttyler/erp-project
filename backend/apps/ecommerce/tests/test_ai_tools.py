from django_tenants.test.cases import TenantTestCase

from apps.core.models import Entity
from apps.ecommerce.ai_tools import marketplace_sync_status
from apps.ecommerce.models import MarketplaceAccount, MarketplaceOrder
from apps.inventory.models import Warehouse


class MarketplaceSyncStatusMetricTests(TenantTestCase):
    def setUp(self):
        self.entity = Entity.objects.create(name="Acme A.Ş.", code="ACME")
        self.warehouse = Warehouse.objects.create(code="ECOM-DEPO", name="E-ticaret Depo")
        self.account = MarketplaceAccount.objects.create(
            platform=MarketplaceAccount.SHOPIFY, name="My Store", entity=self.entity, warehouse=self.warehouse,
            shop_domain="test-shop.myshopify.com", api_secret="x",
        )

    def test_reports_failed_order_count_for_each_active_account(self):
        MarketplaceOrder.objects.create(account=self.account, external_order_id="1", status=MarketplaceOrder.FAILED, error="no listing")
        MarketplaceOrder.objects.create(account=self.account, external_order_id="2", status=MarketplaceOrder.SYNCED)

        outcome = marketplace_sync_status()
        self.assertEqual(len(outcome["result"]["accounts"]), 1)
        self.assertEqual(outcome["result"]["accounts"][0]["failed_order_count"], 1)
        self.assertEqual(outcome["result"]["accounts"][0]["name"], "My Store")

    def test_inactive_accounts_are_excluded(self):
        self.account.is_active = False
        self.account.save()
        outcome = marketplace_sync_status()
        self.assertEqual(outcome["result"]["accounts"], [])
