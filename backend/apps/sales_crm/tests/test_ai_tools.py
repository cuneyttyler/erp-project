from decimal import Decimal

from django_tenants.test.cases import TenantTestCase

from apps.core.models import Item, Party
from apps.inventory.models import Warehouse
from apps.sales_crm.ai_tools import open_leads, open_sales_orders
from apps.sales_crm.models import Lead, SalesOrder, SalesOrderLine


class OpenSalesOrdersMetricTests(TenantTestCase):
    def setUp(self):
        self.customer = Party.objects.create(name="Müşteri A.Ş.", party_type=Party.CUSTOMER)
        self.warehouse = Warehouse.objects.create(code="WH-A", name="Main")
        self.item = Item.objects.create(sku="SO-1", name="Widget")

    def _make_so(self, status):
        so = SalesOrder.objects.create(
            party=self.customer, warehouse=self.warehouse, order_date="2026-07-01",
            expected_date="2026-08-01", status=status,
        )
        SalesOrderLine.objects.create(sales_order=so, item=self.item, quantity_ordered=Decimal("5"), unit_price=Decimal("200.00"))
        return so

    def test_includes_confirmed_and_partially_fulfilled_only(self):
        self._make_so(SalesOrder.DRAFT)
        confirmed = self._make_so(SalesOrder.CONFIRMED)
        partial = self._make_so(SalesOrder.PARTIALLY_FULFILLED)
        self._make_so(SalesOrder.FULFILLED)

        outcome = open_sales_orders()
        ids = {o["id"] for o in outcome["result"]["orders"]}
        self.assertEqual(ids, {confirmed.id, partial.id})

    def test_reports_correct_total_and_customer(self):
        self._make_so(SalesOrder.CONFIRMED)
        outcome = open_sales_orders()
        self.assertEqual(outcome["result"]["orders"][0]["total"], "1000.00")
        self.assertEqual(outcome["result"]["orders"][0]["customer"], "Müşteri A.Ş.")


class OpenLeadsMetricTests(TenantTestCase):
    def test_includes_only_new_and_qualified(self):
        new_lead = Lead.objects.create(name="Lead A", status=Lead.NEW)
        qualified_lead = Lead.objects.create(name="Lead B", status=Lead.QUALIFIED)
        Lead.objects.create(name="Lead C", status=Lead.WON)
        Lead.objects.create(name="Lead D", status=Lead.LOST)

        outcome = open_leads()
        names = {l["name"] for l in outcome["result"]["leads"]}
        self.assertEqual(names, {"Lead A", "Lead B"})
        self.assertEqual(outcome["result"]["count"], 2)
