"""Sales & CRM tests (REQ-CRM-001/002/003)."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import Invoice, Item, Party, User
from apps.inventory import services as inventory_services
from apps.inventory.models import Warehouse
from apps.sales_crm.models import Lead, SalesOrder, SalesOrderLine


class LeadLifecycleTests(TenantTestCase):
    def setUp(self):
        self.lead = Lead.objects.create(name="Acme Inc.", source="web")

    def test_qualify_then_win_converts_to_party(self):
        self.lead.qualify()
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, Lead.QUALIFIED)

        party = Party.objects.create(name="Acme Inc.", party_type=Party.CUSTOMER)
        self.lead.mark_won(party)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, Lead.WON)
        self.assertEqual(self.lead.party, party)

    def test_cannot_win_an_already_closed_lead(self):
        self.lead.mark_lost()
        with self.assertRaises(ValidationError):
            self.lead.mark_won(Party.objects.create(name="X", party_type=Party.CUSTOMER))


class SalesOrderFulfillmentTests(TenantTestCase):
    def setUp(self):
        self.customer = Party.objects.create(name="Acme A.Ş.", party_type=Party.CUSTOMER, payment_terms_days=30)
        self.warehouse = Warehouse.objects.create(code="WH-A", name="Main")
        self.item = Item.objects.create(sku="ITM-1", name="Widget")
        inventory_services.record_receipt(self.item, self.warehouse, Decimal("100.00"), "seed")

        self.order = SalesOrder.objects.create(
            party=self.customer, warehouse=self.warehouse, order_date="2026-01-01"
        )
        self.line = SalesOrderLine.objects.create(
            sales_order=self.order, item=self.item, quantity_ordered=Decimal("10.00"), unit_price=Decimal("25.00")
        )

    def test_cannot_fulfill_a_draft_order(self):
        with self.assertRaises(ValidationError):
            self.order.fulfill([{"line_id": self.line.id, "quantity": Decimal("1.00")}])

    def test_confirm_then_full_fulfillment_marks_order_fulfilled(self):
        self.order.confirm()
        invoice = self.order.fulfill([{"line_id": self.line.id, "quantity": Decimal("10.00")}])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, SalesOrder.FULFILLED)
        self.assertEqual(invoice.status, Invoice.DRAFT)
        self.assertEqual(invoice.party, self.customer)
        self.assertEqual(invoice.total, Decimal("250.00"))

    def test_partial_fulfillment_picks_stock_and_sets_partial_status(self):
        self.order.confirm()
        self.order.fulfill([{"line_id": self.line.id, "quantity": Decimal("4.00")}])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, SalesOrder.PARTIALLY_FULFILLED)
        self.assertEqual(
            inventory_services.get_quantity_on_hand(self.item, self.warehouse), Decimal("96.00")
        )

    def test_cannot_oversell_beyond_available_stock(self):
        # A line can be ordered for more than is currently on hand (e.g. a
        # backorder) -- the fulfill-time stock check is what must reject
        # shipping more than physically available, distinct from the
        # quantity_ordered/quantity_remaining check exercised elsewhere.
        big_line = SalesOrderLine.objects.create(
            sales_order=self.order, item=self.item, quantity_ordered=Decimal("200.00"), unit_price=Decimal("5.00")
        )
        self.order.confirm()
        with self.assertRaises(ValidationError):
            self.order.fulfill([{"line_id": big_line.id, "quantity": Decimal("150.00")}])  # only 100 on hand

    def test_fulfillment_fetched_via_prefetch_reports_status_correctly(self):
        # Regression coverage for the same prefetch-staleness class of bug
        # fixed in purchasing -- applied here proactively rather than
        # discovered via manual testing a second time.
        self.order.confirm()
        order = SalesOrder.objects.prefetch_related("lines__item").get(id=self.order.id)
        order.fulfill([{"line_id": self.line.id, "quantity": Decimal("10.00")}])
        order.refresh_from_db()
        self.assertEqual(order.status, SalesOrder.FULFILLED)


class SalesOrderAPITests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rep", password="x")
        self.customer = Party.objects.create(name="Acme A.Ş.", party_type=Party.CUSTOMER)
        self.warehouse = Warehouse.objects.create(code="WH-A", name="Main")
        self.item = Item.objects.create(sku="ITM-1", name="Widget")
        self.tenant.active_packages = ["sales_crm", "inventory"]
        self.tenant.save()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_fulfill_response_reflects_updated_quantities(self):
        inventory_services.record_receipt(self.item, self.warehouse, Decimal("50.00"), "seed")
        order_resp = self.client.post(
            "/api/v1/sales-crm/sales-orders/",
            {
                "party": self.customer.id,
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
            f"/api/v1/sales-crm/sales-orders/{order_id}/confirm/", HTTP_HOST="tenant.test.com"
        )
        fulfill_resp = self.client.post(
            f"/api/v1/sales-crm/sales-orders/{order_id}/fulfill/",
            {"lines": [{"line_id": line_id, "quantity": "5.00"}]},
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(fulfill_resp.status_code, 200, fulfill_resp.content)
        so_data = fulfill_resp.data["sales_order"]
        self.assertEqual(so_data["status"], "fulfilled")
        self.assertEqual(so_data["lines"][0]["quantity_fulfilled"], "5.00")
        self.assertEqual(fulfill_resp.data["generated_invoice"]["total"], "50.00")

    def test_tenant_without_sales_crm_package_is_forbidden(self):
        self.tenant.active_packages = ["inventory"]
        self.tenant.save()
        response = self.client.get("/api/v1/sales-crm/sales-orders/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 403)
