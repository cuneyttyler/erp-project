from decimal import Decimal

from django_tenants.test.cases import TenantTestCase

from apps.core.models import Item, Party
from apps.inventory.models import Warehouse
from apps.purchasing.ai_tools import open_purchase_orders
from apps.purchasing.models import PurchaseOrder, PurchaseOrderLine


class OpenPurchaseOrdersMetricTests(TenantTestCase):
    def setUp(self):
        self.vendor = Party.objects.create(name="Tedarikçi A.Ş.", party_type=Party.VENDOR)
        self.warehouse = Warehouse.objects.create(code="WH-A", name="Main")
        self.item = Item.objects.create(sku="PUR-1", name="Bolt")

    def _make_po(self, status, expected_date="2026-08-01"):
        po = PurchaseOrder.objects.create(
            party=self.vendor, warehouse=self.warehouse, order_date="2026-07-01",
            expected_date=expected_date, status=status,
        )
        PurchaseOrderLine.objects.create(purchase_order=po, item=self.item, quantity_ordered=Decimal("10"), unit_price=Decimal("100.00"))
        return po

    def test_includes_sent_and_partially_received_only(self):
        self._make_po(PurchaseOrder.DRAFT)
        sent = self._make_po(PurchaseOrder.SENT)
        partial = self._make_po(PurchaseOrder.PARTIALLY_RECEIVED)
        self._make_po(PurchaseOrder.RECEIVED)
        self._make_po(PurchaseOrder.CANCELLED)

        outcome = open_purchase_orders()
        ids = {o["id"] for o in outcome["result"]["orders"]}
        self.assertEqual(ids, {sent.id, partial.id})
        self.assertEqual(outcome["result"]["count"], 2)

    def test_reports_correct_total(self):
        self._make_po(PurchaseOrder.SENT)
        outcome = open_purchase_orders()
        self.assertEqual(outcome["result"]["orders"][0]["total"], "1000.00")
        self.assertEqual(outcome["result"]["orders"][0]["vendor"], "Tedarikçi A.Ş.")
