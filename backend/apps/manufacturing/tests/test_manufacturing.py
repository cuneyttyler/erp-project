"""Manufacturing tests (REQ-MFG-001/002)."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import Item, User
from apps.inventory import services as inventory_services
from apps.inventory.models import Warehouse
from apps.manufacturing.models import BOM, BOMLine, WorkOrder


class WorkOrderCompletionTests(TenantTestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(code="WH-A", name="Main")
        self.finished_good = Item.objects.create(sku="FG-1", name="Assembled Widget")
        self.component_a = Item.objects.create(sku="COMP-A", name="Screw")
        self.component_b = Item.objects.create(sku="COMP-B", name="Bracket")

        self.bom = BOM.objects.create(item=self.finished_good, name="Standard build")
        BOMLine.objects.create(bom=self.bom, component_item=self.component_a, quantity_per=Decimal("4.0000"))
        BOMLine.objects.create(bom=self.bom, component_item=self.component_b, quantity_per=Decimal("1.0000"))

        inventory_services.record_receipt(self.component_a, self.warehouse, Decimal("100.00"), "seed")
        inventory_services.record_receipt(self.component_b, self.warehouse, Decimal("100.00"), "seed")

        self.wo = WorkOrder.objects.create(
            bom=self.bom, warehouse=self.warehouse, quantity_planned=Decimal("10.00"), scheduled_date="2026-01-01"
        )

    def test_cannot_release_a_bom_with_no_lines(self):
        empty_bom = BOM.objects.create(item=self.finished_good, name="Empty")
        wo = WorkOrder.objects.create(
            bom=empty_bom, warehouse=self.warehouse, quantity_planned=Decimal("1.00"), scheduled_date="2026-01-01"
        )
        with self.assertRaises(ValidationError):
            wo.release()

    def test_cannot_complete_a_draft_work_order(self):
        with self.assertRaises(ValidationError):
            self.wo.complete(Decimal("1.00"))

    def test_full_completion_consumes_components_and_produces_finished_good(self):
        self.wo.release()
        self.wo.complete(Decimal("10.00"))
        self.wo.refresh_from_db()

        self.assertEqual(self.wo.status, WorkOrder.COMPLETED)
        self.assertEqual(self.wo.quantity_completed, Decimal("10.00"))
        # 4 per unit x 10 units = 40 consumed from 100
        self.assertEqual(
            inventory_services.get_quantity_on_hand(self.component_a, self.warehouse), Decimal("60.00")
        )
        self.assertEqual(
            inventory_services.get_quantity_on_hand(self.component_b, self.warehouse), Decimal("90.00")
        )
        self.assertEqual(
            inventory_services.get_quantity_on_hand(self.finished_good, self.warehouse), Decimal("10.00")
        )

    def test_partial_completion_sets_in_progress_status(self):
        self.wo.release()
        self.wo.complete(Decimal("3.00"))
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.status, WorkOrder.IN_PROGRESS)
        self.assertEqual(self.wo.quantity_remaining, Decimal("7.00"))

    def test_insufficient_component_stock_blocks_completion_and_consumes_nothing(self):
        # component_b only has 100 on hand; ask for far more than that scales to
        self.wo.quantity_planned = Decimal("1000.00")
        self.wo.save()
        self.wo.release()
        with self.assertRaises(ValidationError):
            self.wo.complete(Decimal("1000.00"))
        # Nothing should have been consumed -- the shortage check runs for
        # ALL lines before any component is picked (models.py's two-pass design).
        self.assertEqual(
            inventory_services.get_quantity_on_hand(self.component_a, self.warehouse), Decimal("100.00")
        )
        self.assertEqual(
            inventory_services.get_quantity_on_hand(self.component_b, self.warehouse), Decimal("100.00")
        )

    def test_cannot_complete_more_than_remaining(self):
        self.wo.release()
        with self.assertRaises(ValidationError):
            self.wo.complete(Decimal("11.00"))


class ManufacturingAPITests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="planner", password="x")
        self.warehouse = Warehouse.objects.create(code="WH-A", name="Main")
        self.finished_good = Item.objects.create(sku="FG-1", name="Assembled Widget")
        self.component = Item.objects.create(sku="COMP-A", name="Screw")
        self.bom = BOM.objects.create(item=self.finished_good, name="Standard build")
        BOMLine.objects.create(bom=self.bom, component_item=self.component, quantity_per=Decimal("2.0000"))
        inventory_services.record_receipt(self.component, self.warehouse, Decimal("50.00"), "seed")

        self.tenant.active_packages = ["manufacturing", "inventory"]
        self.tenant.save()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_release_then_complete_via_api(self):
        wo = WorkOrder.objects.create(
            bom=self.bom, warehouse=self.warehouse, quantity_planned=Decimal("5.00"), scheduled_date="2026-01-01"
        )
        self.client.post(f"/api/v1/manufacturing/work-orders/{wo.id}/release/", HTTP_HOST="tenant.test.com")
        response = self.client.post(
            f"/api/v1/manufacturing/work-orders/{wo.id}/complete/",
            {"quantity": "5.00"},
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["quantity_completed"], "5.00")

    def test_tenant_without_manufacturing_package_is_forbidden(self):
        self.tenant.active_packages = ["inventory"]
        self.tenant.save()
        response = self.client.get("/api/v1/manufacturing/work-orders/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 403)
