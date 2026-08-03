"""ShopifyAdapter tests (REQ-ECOM-001/003) -- mocks `requests` so these never
make a real network call (no live Shopify credentials exist in this
environment, see docs/notes.md). What's under test: the request shape sent
to Shopify's documented API and the response parsing, not Shopify's API
itself."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from apps.ecommerce.adapters import ShopifyAdapter


def _fake_account(**overrides):
    defaults = {"shop_domain": "test-shop.myshopify.com", "api_secret": "shpat_test123"}
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _fake_response(json_data, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.raise_for_status.side_effect = None
    return response


class ShopifyAdapterFetchOrdersTests(SimpleTestCase):
    def test_fetch_new_orders_hits_the_documented_endpoint_with_auth_header(self):
        account = _fake_account()
        adapter = ShopifyAdapter(account)
        with patch("apps.ecommerce.adapters.requests.get", return_value=_fake_response({"orders": []})) as mock_get:
            adapter.fetch_new_orders(since=timezone.now())
        call = mock_get.call_args
        self.assertEqual(call.args[0], "https://test-shop.myshopify.com/admin/api/2024-01/orders.json")
        self.assertEqual(call.kwargs["headers"]["X-Shopify-Access-Token"], "shpat_test123")

    def test_parses_orders_into_external_order_dataclasses(self):
        account = _fake_account()
        adapter = ShopifyAdapter(account)
        raw = {
            "orders": [
                {
                    "id": 5551234,
                    "email": "buyer@example.com",
                    "customer": {"first_name": "Ayşe", "last_name": "Yılmaz", "email": "buyer@example.com"},
                    "line_items": [
                        {"sku": "SKU-1", "quantity": 2, "price": "49.90"},
                        {"sku": "", "quantity": 1, "price": "10.00"},  # no SKU -- excluded
                    ],
                }
            ]
        }
        with patch("apps.ecommerce.adapters.requests.get", return_value=_fake_response(raw)):
            orders = adapter.fetch_new_orders(since=timezone.now())

        self.assertEqual(len(orders), 1)
        order = orders[0]
        self.assertEqual(order.external_order_id, "5551234")
        self.assertEqual(order.customer_email, "buyer@example.com")
        self.assertEqual(order.customer_name, "Ayşe Yılmaz")
        self.assertEqual(len(order.lines), 1)
        self.assertEqual(order.lines[0].sku, "SKU-1")
        self.assertEqual(order.lines[0].quantity, Decimal("2"))
        self.assertEqual(order.lines[0].unit_price, Decimal("49.90"))

    def test_falls_back_to_order_level_email_when_no_customer_object(self):
        account = _fake_account()
        adapter = ShopifyAdapter(account)
        raw = {"orders": [{"id": 1, "email": "guest@example.com", "line_items": []}]}
        with patch("apps.ecommerce.adapters.requests.get", return_value=_fake_response(raw)):
            orders = adapter.fetch_new_orders(since=timezone.now())
        self.assertEqual(orders[0].customer_email, "guest@example.com")
        self.assertEqual(orders[0].customer_name, "")

    def test_raises_on_non_2xx_response(self):
        account = _fake_account()
        adapter = ShopifyAdapter(account)
        response = _fake_response({}, status_code=401)
        response.raise_for_status.side_effect = Exception("401 Unauthorized")
        with patch("apps.ecommerce.adapters.requests.get", return_value=response):
            with self.assertRaises(Exception):
                adapter.fetch_new_orders(since=timezone.now())


class ShopifyAdapterPushStockTests(SimpleTestCase):
    def test_push_stock_level_posts_the_documented_payload(self):
        account = _fake_account()
        adapter = ShopifyAdapter(account)
        listing = SimpleNamespace(external_variant_id="999", external_location_id="111")
        with patch("apps.ecommerce.adapters.requests.post", return_value=_fake_response({})) as mock_post:
            adapter.push_stock_level(listing, Decimal("42"))
        call = mock_post.call_args
        self.assertEqual(call.args[0], "https://test-shop.myshopify.com/admin/api/2024-01/inventory_levels/set.json")
        self.assertEqual(call.kwargs["json"], {"location_id": "111", "inventory_item_id": "999", "available": 42})
