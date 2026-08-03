"""HTTP-level tests for the e-commerce API (REQ-ECOM-001/003) -- package
gating, that api_secret never comes back out of the API, and that the
sync-orders/push-stock actions wire into services.py correctly. Sync
correctness itself is covered by test_services.py."""

from unittest.mock import patch

from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import Entity, User
from apps.ecommerce.models import MarketplaceAccount
from apps.inventory.models import Warehouse


class EcommerceViewTestBase(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="x")
        self.client = APIClient()
        self.entity = Entity.objects.create(name="Acme A.Ş.", code="ACME")
        self.warehouse = Warehouse.objects.create(code="ECOM-DEPO", name="E-ticaret Depo")
        self.tenant.active_packages = ["ecommerce"]
        self.tenant.save()


class PackageGatingTests(EcommerceViewTestBase):
    def test_requires_authentication(self):
        response = self.client.get("/api/v1/ecommerce/accounts/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 403)

    def test_blocked_without_active_ecommerce_package(self):
        self.tenant.active_packages = []
        self.tenant.save()
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/ecommerce/accounts/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 403)

    def test_allowed_with_active_ecommerce_package(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/ecommerce/accounts/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 200)


class MarketplaceAccountViewTests(EcommerceViewTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user)

    def test_api_secret_is_accepted_but_never_returned(self):
        response = self.client.post(
            "/api/v1/ecommerce/accounts/",
            {
                "platform": "shopify",
                "name": "My Store",
                "entity": self.entity.id,
                "warehouse": self.warehouse.id,
                "shop_domain": "test-shop.myshopify.com",
                "api_key": "key123",
                "api_secret": "supersecret",
            },
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn("api_secret", response.data)
        self.assertNotIn("api_key", response.data)

        account = MarketplaceAccount.objects.get(id=response.data["id"])
        self.assertEqual(account.api_secret, "supersecret")

        list_response = self.client.get("/api/v1/ecommerce/accounts/", HTTP_HOST="tenant.test.com")
        for row in list_response.data.get("results", list_response.data):
            self.assertNotIn("api_secret", row)

    def test_sync_orders_action_calls_the_service_and_returns_its_result(self):
        account = MarketplaceAccount.objects.create(
            platform=MarketplaceAccount.SHOPIFY, name="Store", entity=self.entity, warehouse=self.warehouse,
            shop_domain="test-shop.myshopify.com", api_secret="x",
        )
        with patch("apps.ecommerce.views.services.sync_orders", return_value={"created": 2, "skipped": 1, "failed": 0}):
            response = self.client.post(f"/api/v1/ecommerce/accounts/{account.id}/sync-orders/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["created"], 2)

    def test_sync_orders_action_degrades_to_502_on_adapter_failure(self):
        account = MarketplaceAccount.objects.create(
            platform=MarketplaceAccount.SHOPIFY, name="Store", entity=self.entity, warehouse=self.warehouse,
            shop_domain="test-shop.myshopify.com", api_secret="x",
        )
        with patch("apps.ecommerce.views.services.sync_orders", side_effect=Exception("timeout")):
            response = self.client.post(f"/api/v1/ecommerce/accounts/{account.id}/sync-orders/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 502)

    def test_push_stock_action_calls_the_service(self):
        account = MarketplaceAccount.objects.create(
            platform=MarketplaceAccount.SHOPIFY, name="Store", entity=self.entity, warehouse=self.warehouse,
            shop_domain="test-shop.myshopify.com", api_secret="x",
        )
        with patch("apps.ecommerce.views.services.push_stock_levels", return_value={"pushed": 3, "failed": 0}):
            response = self.client.post(f"/api/v1/ecommerce/accounts/{account.id}/push-stock/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pushed"], 3)
