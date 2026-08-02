from decimal import Decimal

from django_tenants.test.cases import TenantTestCase

from apps.core.models import Account, Entity, Item, User
from apps.inventory import services as inventory_services
from apps.inventory.models import Warehouse
from apps.pos import services
from apps.pos.ai_tools import open_pos_shifts, todays_pos_sales
from apps.pos.models import POSPayment, POSShift, Store, Till


class POSMetricsTests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cashier", password="x")
        self.entity = Entity.objects.create(name="Acme Perakende", code="ACME")
        self.warehouse = Warehouse.objects.create(code="MAG1", name="Mağaza 1 Depo")
        self.store = Store.objects.create(entity=self.entity, warehouse=self.warehouse, code="S1", name="Kadıköy")
        self.till = Till.objects.create(store=self.store, code="T1", name="Kasa 1")
        Account.objects.create(code="100", name="Kasa", account_type=Account.ASSET, entity=self.entity)
        Account.objects.create(code="600", name="Yurtiçi Satışlar", account_type=Account.REVENUE, entity=self.entity)
        self.item = Item.objects.create(sku="SKU-1", name="Widget")
        inventory_services.record_receipt(item=self.item, warehouse=self.warehouse, quantity=Decimal("50"), reference="seed")

    def test_todays_pos_sales_sums_completed_sales(self):
        shift = POSShift.objects.create(till=self.till, opened_by=self.user, opening_cash=Decimal("0"))
        services.checkout(
            shift,
            lines=[{"item_id": self.item.id, "quantity": "2", "unit_price": "50.00"}],
            payments=[{"method": POSPayment.CASH, "amount": "100.00"}],
            user=self.user,
        )
        outcome = todays_pos_sales()
        self.assertEqual(outcome["result"]["transaction_count"], 1)
        self.assertEqual(outcome["result"]["gross_sales"], "100.00")

    def test_todays_pos_sales_with_no_sales_returns_zero(self):
        outcome = todays_pos_sales()
        self.assertEqual(outcome["result"]["transaction_count"], 0)
        self.assertEqual(outcome["result"]["gross_sales"], "0.00")

    def test_open_pos_shifts_lists_only_open_ones(self):
        open_shift = POSShift.objects.create(till=self.till, opened_by=self.user, opening_cash=Decimal("0"))
        closed_shift = POSShift.objects.create(till=self.till, opened_by=self.user, opening_cash=Decimal("0"))
        closed_shift.close(Decimal("0"))

        outcome = open_pos_shifts()
        self.assertEqual(outcome["result"]["count"], 1)
        self.assertEqual(outcome["result"]["shifts"][0]["id"], open_shift.id)
