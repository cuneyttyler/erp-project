from decimal import Decimal

from django_tenants.test.cases import TenantTestCase

from apps.core.models import Item
from apps.inventory import services as inventory_services
from apps.inventory.models import Warehouse
from apps.manufacturing.ai_tools import pending_work_orders
from apps.manufacturing.models import BOM, BOMLine, WorkOrder


class PendingWorkOrdersMetricTests(TenantTestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(code="WH-A", name="Main")
        self.finished_good = Item.objects.create(sku="AI-FG-1", name="Assembled Widget")
        self.component = Item.objects.create(sku="AI-COMP-1", name="Screw")
        self.bom = BOM.objects.create(item=self.finished_good, name="Standard build")
        BOMLine.objects.create(bom=self.bom, component_item=self.component, quantity_per=Decimal("1.0000"))
        inventory_services.record_receipt(self.component, self.warehouse, Decimal("100.00"), "seed")

    def _make_wo(self, quantity=Decimal("10.00")):
        return WorkOrder.objects.create(
            bom=self.bom, warehouse=self.warehouse, quantity_planned=quantity, scheduled_date="2026-08-01"
        )

    def test_excludes_draft_completed_and_cancelled(self):
        self._make_wo()  # draft
        released = self._make_wo()
        released.release()
        completed = self._make_wo()
        completed.release()
        completed.complete(Decimal("10.00"))

        outcome = pending_work_orders()
        ids = {o["id"] for o in outcome["result"]["work_orders"]}
        self.assertEqual(ids, {released.id})

    def test_reports_planned_and_completed_quantities(self):
        wo = self._make_wo(Decimal("10.00"))
        wo.release()
        wo.complete(Decimal("4.00"))  # partial -> in_progress
        outcome = pending_work_orders()
        row = outcome["result"]["work_orders"][0]
        self.assertEqual(row["quantity_planned"], "10.00")
        self.assertEqual(row["quantity_completed"], "4.00")
        self.assertEqual(row["item"], "AI-FG-1")
