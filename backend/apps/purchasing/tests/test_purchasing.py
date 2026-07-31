"""Purchasing tests (REQ-PUR-001/002/005)."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import Bill, Item, Party, User
from apps.inventory.models import StockMove, Warehouse
from apps.purchasing.models import PurchaseOrder, PurchaseOrderLine


class ApprovalWorkflowTests(TenantTestCase):
    def setUp(self):
        self.vendor = Party.objects.create(name="Tedarikçi Ltd.", party_type=Party.VENDOR)
        self.warehouse = Warehouse.objects.create(code="WH-A", name="Main")
        self.item = Item.objects.create(sku="ITM-1", name="Widget")
        self.user = User.objects.create_user(username="buyer", password="x")

    def _make_order(self, unit_price, quantity=1):
        order = PurchaseOrder.objects.create(party=self.vendor, warehouse=self.warehouse, order_date="2026-01-01")
        PurchaseOrderLine.objects.create(
            purchase_order=order, item=self.item, quantity_ordered=quantity, unit_price=unit_price
        )
        return order

    def test_small_order_can_be_sent_without_approval(self):
        order = self._make_order(Decimal("50.00"))
        order.mark_sent()
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.SENT)

    def test_large_order_requires_approval_before_sending(self):
        order = self._make_order(Decimal("20000.00"))
        self.assertTrue(order.requires_approval)
        with self.assertRaises(ValidationError):
            order.mark_sent()

    def test_approved_large_order_can_be_sent(self):
        order = self._make_order(Decimal("20000.00"))
        order.approve(self.user)
        order.mark_sent()
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.SENT)
        self.assertEqual(order.approved_by, self.user)


class ReceivingTests(TenantTestCase):
    def setUp(self):
        self.vendor = Party.objects.create(name="Tedarikçi Ltd.", party_type=Party.VENDOR, payment_terms_days=30)
        self.warehouse = Warehouse.objects.create(code="WH-A", name="Main")
        self.item = Item.objects.create(sku="ITM-1", name="Widget")
        self.order = PurchaseOrder.objects.create(
            party=self.vendor, warehouse=self.warehouse, order_date="2026-01-01"
        )
        self.line = PurchaseOrderLine.objects.create(
            purchase_order=self.order, item=self.item, quantity_ordered=Decimal("10.00"), unit_price=Decimal("25.00")
        )
        self.order.mark_sent()

    def test_partial_receipt_updates_status_and_stock(self):
        self.order.receive([{"line_id": self.line.id, "quantity": Decimal("4.00")}])
        self.order.refresh_from_db()
        self.line.refresh_from_db()
        self.assertEqual(self.order.status, PurchaseOrder.PARTIALLY_RECEIVED)
        self.assertEqual(self.line.quantity_received, Decimal("4.00"))
        stock = sum(m.quantity for m in StockMove.objects.filter(item=self.item, warehouse=self.warehouse))
        self.assertEqual(stock, Decimal("4.00"))

    def test_full_receipt_marks_order_received(self):
        self.order.receive([{"line_id": self.line.id, "quantity": Decimal("10.00")}])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, PurchaseOrder.RECEIVED)

    def test_full_receipt_marks_received_even_when_fetched_via_prefetch(self):
        # Regression test: PurchaseOrderViewSet.get_object() fetches through
        # a .prefetch_related("lines__item") queryset, exactly like this --
        # receive() used to check completion via the cached `self.lines.all()`
        # snapshot (taken before this call's own updates), so a fully-received
        # order was misreported as partially_received. See models.py's
        # `fresh_lines` comment in receive().
        order = PurchaseOrder.objects.prefetch_related("lines__item").get(id=self.order.id)
        order.receive([{"line_id": self.line.id, "quantity": Decimal("10.00")}])
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.RECEIVED)

    def test_receiving_generates_a_draft_bill_with_correct_total(self):
        bill = self.order.receive([{"line_id": self.line.id, "quantity": Decimal("4.00")}])
        self.assertEqual(bill.status, Bill.DRAFT)
        self.assertEqual(bill.party, self.vendor)
        self.assertEqual(bill.total, Decimal("100.00"))  # 4 * 25.00

    def test_cannot_receive_more_than_remaining(self):
        with self.assertRaises(ValidationError):
            self.order.receive([{"line_id": self.line.id, "quantity": Decimal("11.00")}])

    def test_cannot_receive_against_a_draft_order(self):
        draft_order = PurchaseOrder.objects.create(
            party=self.vendor, warehouse=self.warehouse, order_date="2026-01-01"
        )
        line = PurchaseOrderLine.objects.create(
            purchase_order=draft_order, item=self.item, quantity_ordered=Decimal("5.00"), unit_price=Decimal("10.00")
        )
        with self.assertRaises(ValidationError):
            draft_order.receive([{"line_id": line.id, "quantity": Decimal("1.00")}])


class PurchaseOrderAPITests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="buyer", password="x")
        self.vendor = Party.objects.create(name="Tedarikçi Ltd.", party_type=Party.VENDOR)
        self.warehouse = Warehouse.objects.create(code="WH-A", name="Main")
        self.item = Item.objects.create(sku="ITM-1", name="Widget")
        self.tenant.active_packages = ["purchasing", "inventory"]
        self.tenant.save()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_order_via_api(self):
        response = self.client.post(
            "/api/v1/purchasing/purchase-orders/",
            {
                "party": self.vendor.id,
                "warehouse": self.warehouse.id,
                "order_date": "2026-01-01",
                "lines": [{"item": self.item.id, "quantity_ordered": "5.00", "unit_price": "12.50"}],
            },
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 201, response.content)
        # response.data holds the DRF-coerced string, not a Decimal.
        self.assertEqual(response.data["total"], "62.50")

    def test_receive_response_reflects_updated_quantities_not_stale_cache(self):
        # Regression test for the response-serialization half of the same
        # prefetch-staleness bug covered in ReceivingTests -- this exercises
        # the actual HTTP response body a client sees, not just the model.
        order_resp = self.client.post(
            "/api/v1/purchasing/purchase-orders/",
            {
                "party": self.vendor.id,
                "warehouse": self.warehouse.id,
                "order_date": "2026-01-01",
                "lines": [{"item": self.item.id, "quantity_ordered": "5.00", "unit_price": "10.00"}],
            },
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        order_id = order_resp.data["id"]
        line_id = order_resp.data["lines"][0]["id"]
        self.client.post(
            f"/api/v1/purchasing/purchase-orders/{order_id}/send_document/",
            HTTP_HOST="tenant.test.com",
        )
        receive_resp = self.client.post(
            f"/api/v1/purchasing/purchase-orders/{order_id}/receive/",
            {"lines": [{"line_id": line_id, "quantity": "5.00"}]},
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(receive_resp.status_code, 200, receive_resp.content)
        po_data = receive_resp.data["purchase_order"]
        self.assertEqual(po_data["status"], "received")
        self.assertEqual(po_data["lines"][0]["quantity_received"], "5.00")
        self.assertEqual(po_data["lines"][0]["quantity_remaining"], "0.00")

    def test_tenant_without_purchasing_package_is_forbidden(self):
        self.tenant.active_packages = ["inventory"]
        self.tenant.save()
        response = self.client.get("/api/v1/purchasing/purchase-orders/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 403)
