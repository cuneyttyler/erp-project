"""HTTP-level tests for the POS API (REQ-POS-001/002/004/005) -- package
gating, auth, and that the endpoints wire correctly into services.py.
Checkout/return correctness itself is covered by test_pos.py."""

from decimal import Decimal

from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import Account, Entity, Item, User
from apps.inventory import services as inventory_services
from apps.inventory.models import Warehouse
from apps.pos.models import POSPayment, POSSale, POSShift, Store, Till


class POSViewTestBase(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cashier", password="x")
        self.client = APIClient()

        self.entity = Entity.objects.create(name="Acme Perakende", code="ACME")
        self.warehouse = Warehouse.objects.create(code="MAG1", name="Mağaza 1 Depo")
        self.store = Store.objects.create(entity=self.entity, warehouse=self.warehouse, code="S1", name="Kadıköy")
        self.till = Till.objects.create(store=self.store, code="T1", name="Kasa 1")

        Account.objects.create(code="100", name="Kasa", account_type=Account.ASSET, entity=self.entity)
        Account.objects.create(code="102", name="Bankalar", account_type=Account.ASSET, entity=self.entity)
        Account.objects.create(code="600", name="Yurtiçi Satışlar", account_type=Account.REVENUE, entity=self.entity)
        Account.objects.create(code="610", name="Satıştan İadeler (-)", account_type=Account.REVENUE, entity=self.entity)

        self.item = Item.objects.create(sku="SKU-1", name="Widget")
        inventory_services.record_receipt(item=self.item, warehouse=self.warehouse, quantity=Decimal("50"), reference="seed")

        self.tenant.active_packages = ["pos"]
        self.tenant.save()


class PackageGatingTests(POSViewTestBase):
    def test_requires_authentication(self):
        response = self.client.get("/api/v1/pos/shifts/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 403)

    def test_blocked_without_active_pos_package(self):
        self.tenant.active_packages = []
        self.tenant.save()
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/pos/shifts/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 403)

    def test_allowed_with_active_pos_package(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/pos/shifts/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 200)


class ShiftLifecycleViewTests(POSViewTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user)

    def test_opening_a_shift_sets_opened_by_from_the_request_user(self):
        response = self.client.post(
            "/api/v1/pos/shifts/", {"till": self.till.id, "opening_cash": "500.00"}, format="json", HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(response.status_code, 201)
        shift = POSShift.objects.get(id=response.data["id"])
        self.assertEqual(shift.opened_by, self.user)

    def test_checkout_endpoint_creates_a_sale(self):
        shift = POSShift.objects.create(till=self.till, opened_by=self.user, opening_cash=Decimal("500.00"))
        response = self.client.post(
            f"/api/v1/pos/shifts/{shift.id}/checkout/",
            {
                "lines": [{"item_id": self.item.id, "quantity": "2", "unit_price": "50.00"}],
                "payments": [{"method": "cash", "amount": "100.00"}],
            },
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["subtotal"], "100.00")
        self.assertEqual(POSSale.objects.count(), 1)

    def test_checkout_endpoint_returns_400_on_insufficient_stock(self):
        shift = POSShift.objects.create(till=self.till, opened_by=self.user, opening_cash=Decimal("500.00"))
        response = self.client.post(
            f"/api/v1/pos/shifts/{shift.id}/checkout/",
            {
                "lines": [{"item_id": self.item.id, "quantity": "9999", "unit_price": "50.00"}],
                "payments": [{"method": "cash", "amount": "499950.00"}],
            },
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 400)

    def test_close_endpoint_and_z_report_endpoint(self):
        shift = POSShift.objects.create(till=self.till, opened_by=self.user, opening_cash=Decimal("500.00"))
        self.client.post(
            f"/api/v1/pos/shifts/{shift.id}/checkout/",
            {
                "lines": [{"item_id": self.item.id, "quantity": "2", "unit_price": "50.00"}],
                "payments": [{"method": "cash", "amount": "100.00"}],
            },
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        close_response = self.client.post(
            f"/api/v1/pos/shifts/{shift.id}/close/", {"closing_cash_counted": "600.00"}, format="json", HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(close_response.status_code, 200)
        self.assertEqual(close_response.data["status"], "closed")

        report_response = self.client.get(f"/api/v1/pos/shifts/{shift.id}/z-report/", HTTP_HOST="tenant.test.com")
        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(report_response.data["net_sales"], "100.00")
        self.assertEqual(report_response.data["cash_discrepancy"], "0.00")


class ReturnViewTests(POSViewTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user)
        self.shift = POSShift.objects.create(till=self.till, opened_by=self.user, opening_cash=Decimal("500.00"))
        checkout_response = self.client.post(
            f"/api/v1/pos/shifts/{self.shift.id}/checkout/",
            {
                "lines": [{"item_id": self.item.id, "quantity": "2", "unit_price": "50.00"}],
                "payments": [{"method": "cash", "amount": "100.00"}],
            },
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.sale_id = checkout_response.data["id"]
        self.line_id = checkout_response.data["lines"][0]["id"]

    def test_return_endpoint_creates_a_return_and_updates_sale_status(self):
        response = self.client.post(
            f"/api/v1/pos/sales/{self.sale_id}/return/",
            {"lines": [{"sale_line_id": self.line_id, "quantity": "2"}], "refund_method": "cash"},
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 201, response.data)
        sale = POSSale.objects.get(id=self.sale_id)
        self.assertEqual(sale.status, POSSale.RETURNED)

    def test_return_endpoint_returns_400_over_returning(self):
        response = self.client.post(
            f"/api/v1/pos/sales/{self.sale_id}/return/",
            {"lines": [{"sale_line_id": self.line_id, "quantity": "99"}], "refund_method": "cash"},
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 400)
