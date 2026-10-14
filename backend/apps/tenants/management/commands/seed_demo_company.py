"""
Creates a demonstration organization with realistic history: "Demir Yapı
Market A.Ş.", an Istanbul building-materials wholesaler with a retail shop,
a small production line (ready-mixed plaster) and a marketplace storefront.

Everything is created through the same model methods and services the app
uses -- purchase orders are received (which moves stock and raises the
vendor bill), sales orders are shipped (which picks stock and raises the
invoice), POS sales go through the checkout service (which posts to the
ledger), payroll runs are calculated by the payroll engine -- so stock
levels, bills, invoices, payslips and postings agree with each other. Each
operation runs "at" its date in the past (django.utils.timezone.now is
patched per operation), so dates, ages and created timestamps are those of
a business that has been running since April.

A last handful of actions are performed through the API views, as named
users, so the audit log opens with real entries rather than an empty page.

The names are invented. Any resemblance to a real company is accidental.

    DEMO_PASSWORD=... ADMIN_PASSWORD=... python manage.py seed_demo_company \\
        --schema demirmarket --domain <hostname> [--take-over-domain]
"""

import heapq
import os
import random
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.tenants.management.commands.bootstrap_tenant import ALL_PACKAGES
from apps.tenants.models import Client, Domain

COMPANY = "Demir Yapı Market A.Ş."
VOLUME = 2.0
ORDERS_PER_MONTH = 40
PRICE_UPLIFT = Decimal("1.07")  # list prices -> ~31% gross margin
START = date(2026, 4, 1)
D = Decimal


def money(value) -> Decimal:
    return D(value).quantize(D("0.01"), rounding=ROUND_HALF_UP)


@contextmanager
def at(day: date, hour: int = 10, minute: int = 0):
    """Runs the block as if it were `day` at `hour:minute` (local time)."""
    moment = timezone.make_aware(datetime.combine(day, time(hour, minute)))
    with patch("django.utils.timezone.now", return_value=moment):
        yield


# -- master data -------------------------------------------------------------
# (sku, name, unit, cost, price, vendor key, b2b units/month, sold in shop)
ITEMS = [
    ("CEM-50", "Portland Çimento 50 kg", "torba", 168, 215, "cimento", 1600, True),
    ("CEM-25", "Beyaz Çimento 25 kg", "torba", 142, 189, "cimento", 420, True),
    ("HRC-25", "Hazır Yapı Harcı 25 kg", "torba", 96, 132, "cimento", 900, True),
    ("ALC-35", "Saten Alçı 35 kg", "torba", 118, 158, "alci", 520, True),
    ("ALC-25", "Kartonpiyer Alçısı 25 kg", "torba", 84, 115, "alci", 240, True),
    ("SRM-01", "Seramik Karo 60x60 Mat Gri", "m²", 265, 349, "seramik", 1450, False),
    ("SRM-02", "Seramik Karo 30x60 Beyaz Parlak", "m²", 198, 262, "seramik", 980, False),
    ("SRM-03", "Granit Seramik 60x120 Antrasit", "m²", 412, 545, "seramik", 520, False),
    ("YPS-25", "Seramik Yapıştırıcı 25 kg", "torba", 128, 175, "kimya", 1100, True),
    ("DRZ-05", "Derz Dolgu 5 kg Gri", "kova", 92, 129, "kimya", 640, True),
    ("BOY-15", "İç Cephe Boyası 15 L Beyaz", "kova", 1180, 1595, "boya", 260, True),
    ("BOY-20", "Dış Cephe Boyası 20 L", "kova", 1890, 2490, "boya", 140, True),
    ("AST-15", "Astar 15 L", "kova", 640, 865, "boya", 180, True),
    ("FRC-01", "Boya Fırçası Set 3'lü", "set", 74, 119, "hirdavat", 120, True),
    ("RLO-25", "Rulo 25 cm", "adet", 58, 95, "hirdavat", 160, True),
    ("DMR-12", "İnşaat Demiri Ø12 (12 m)", "adet", 312, 384, "celik", 900, False),
    ("DMR-08", "İnşaat Demiri Ø8 (12 m)", "adet", 141, 176, "celik", 1150, False),
    ("CVD-01", "Çelik Dübel 8x80 (100'lü)", "paket", 118, 169, "hirdavat", 210, True),
    ("VDA-01", "Sunta Vidası 4x40 (500'lü)", "kutu", 135, 189, "hirdavat", 190, True),
    ("MTK-01", "Matkap Ucu Seti 13 Parça", "set", 285, 399, "hirdavat", 45, True),
    ("XPS-03", "XPS Isı Yalıtım Levhası 3 cm", "m²", 118, 159, "yalitim", 2400, False),
    ("TSY-05", "Taşyünü Levha 5 cm", "m²", 146, 198, "yalitim", 1300, False),
    ("PVC-10", "PVC Atık Su Borusu Ø100 (3 m)", "adet", 152, 209, "yalitim", 380, True),
    ("SLK-25", "Silis Kumu 25 kg", "torba", 38, 55, "cimento", 0, False),
    ("KTK-01", "Sıva Katkı Maddesi 1 kg", "paket", 46, 70, "kimya", 0, False),
    ("TRB-25", "Boş Kraft Torba 25 kg", "adet", 6, 9, "ambalaj", 0, False),
    ("HSV-25", "Demir Hazır Sıva 25 kg", "torba", 0, 139, None, 700, True),
]
PRODUCED = "HSV-25"
BOM_COMPONENTS = [("CEM-50", "0.20"), ("SLK-25", "0.60"), ("KTK-01", "0.10"), ("TRB-25", "1")]

VENDORS = {
    "cimento": ("Marmara Çimento Sanayi A.Ş.", 45),
    "alci": ("Eskişehir Alçı ve Yapı Kimyasalları A.Ş.", 30),
    "seramik": ("Ege Seramik Dağıtım Ltd. Şti.", 60),
    "kimya": ("Başak Yapı Kimyasalları A.Ş.", 45),
    "boya": ("Renktaş Boya Sanayi A.Ş.", 60),
    "hirdavat": ("Çelikoğlu Hırdavat Toptan Ltd. Şti.", 30),
    "celik": ("Anadolu Demir Çelik Ticaret A.Ş.", 30),
    "yalitim": ("Kuzey Yalıtım Malzemeleri A.Ş.", 45),
    "ambalaj": ("Trakya Ambalaj Sanayi Ltd. Şti.", 30),
}

# (name, payment terms, how reliably they pay: 0..1, order weight)
CUSTOMERS = [
    ("Anadolu Yapı Malzemeleri A.Ş.", 30, 0.95, 5),
    ("Ege İnşaat Taahhüt Ltd. Şti.", 45, 0.55, 4),
    ("Karadeniz Konut Yapı A.Ş.", 60, 0.9, 4),
    ("Marmara Proje İnşaat A.Ş.", 30, 0.92, 3),
    ("Başkent Yapı Kooperatifi", 45, 0.85, 2),
    ("Toros Mimarlık ve Dekorasyon Ltd. Şti.", 30, 0.97, 2),
    ("Akdeniz Otel İşletmeleri A.Ş.", 60, 0.8, 2),
    ("Boğaziçi Restorasyon Ltd. Şti.", 30, 0.9, 2),
    ("Kapadokya Turizm İnşaat A.Ş.", 45, 0.6, 1),
    ("Trakya Altyapı Ltd. Şti.", 30, 0.93, 2),
    ("Uludağ Peyzaj ve Bahçe Ltd. Şti.", 30, 0.95, 1),
    ("Yıldız Tadilat Hizmetleri", 15, 0.75, 2),
]

EMPLOYEES = [
    ("Hasan", "Demir", "Genel Müdür", "Yönetim", "2015-03-02", 185000),
    ("Ayşe", "Demir", "Finans ve Operasyon Direktörü", "Yönetim", "2016-09-12", 142000),
    ("Mehmet", "Kaya", "Muhasebe Müdürü", "Muhasebe", "2018-01-15", 98000),
    ("Elif", "Şahin", "Muhasebe Uzmanı", "Muhasebe", "2021-04-05", 61000),
    ("Burak", "Öztürk", "Muhasebe Uzmanı", "Muhasebe", "2023-02-13", 52000),
    ("Zeynep", "Arslan", "Satış Müdürü", "Satış", "2017-06-01", 112000),
    ("Emre", "Çelik", "Kurumsal Satış Temsilcisi", "Satış", "2020-10-19", 68000),
    ("Selin", "Aydın", "Kurumsal Satış Temsilcisi", "Satış", "2022-03-07", 63000),
    ("Kerem", "Yılmaz", "Satış Destek Uzmanı", "Satış", "2024-01-08", 47000),
    ("Murat", "Koç", "Depo Şefi", "Depo", "2016-04-11", 72000),
    ("Ali", "Erdoğan", "Depo Görevlisi", "Depo", "2019-07-22", 41000),
    ("Hakan", "Polat", "Forklift Operatörü", "Depo", "2021-11-01", 43500),
    ("Serkan", "Kurt", "Sevkiyat Sorumlusu", "Depo", "2020-02-17", 47500),
    ("Can", "Yıldız", "Mağaza Müdürü", "Mağaza", "2019-05-06", 76000),
    ("Deniz", "Acar", "Kasiyer", "Mağaza", "2023-06-12", 38500),
    ("Gizem", "Tekin", "Kasiyer", "Mağaza", "2024-09-02", 37500),
    ("Ozan", "Bulut", "Mağaza Satış Danışmanı", "Mağaza", "2022-08-15", 41000),
    ("İbrahim", "Güneş", "Üretim Şefi", "Üretim", "2018-10-01", 69000),
    ("Volkan", "Avcı", "Üretim Operatörü", "Üretim", "2021-03-15", 44000),
    ("Recep", "Kaplan", "Üretim Operatörü", "Üretim", "2026-05-04", 42000),
    ("Tuba", "Özdemir", "E-Ticaret Uzmanı", "E-Ticaret", "2023-11-20", 56000),
    ("Ece", "Korkmaz", "İnsan Kaynakları Uzmanı", "Yönetim", "2022-01-10", 58000),
    ("Onur", "Yavuz", "Satın Alma Uzmanı", "Satın Alma", "2020-06-08", 64000),
    ("Pınar", "Uçar", "Satın Alma Uzmanı", "Satın Alma", "2026-07-01", 52000),
]

LEAD_SOURCES = ["Fuar (Yapı Fuarı İstanbul)", "Web sitesi", "Referans", "Bayi önerisi", "Telefon", "Trendyol mağazası"]
LEAD_NAMES = [
    "Lale Konutları — 120 daire yalıtım işi", "Mavi Ev Tadilat — seramik ve boya", "Kuzey Lojistik deposu — zemin işleri",
    "Gölbaşı Villaları — dış cephe", "Sahil Otel yenileme — ıslak hacimler", "Okul binası güçlendirme — demir ve çimento",
    "Çamlıca Sitesi — çatı ve yalıtım", "Atölye 34 — iç mekan boya", "Belde Belediyesi — park ve peyzaj",
    "Yeni Hastane ek binası — alçı ve boya", "Merkez Ofis tadilatı — seramik", "Bahçeşehir konut projesi",
    "Sapanca bungalovları — dış cephe", "Kadıköy apartman yenileme", "Tuzla fabrika ek binası — XPS",
    "Kartal okul spor salonu", "Pendik AVM mağaza tadilatı", "Bursa şantiye — demir tedariki",
]


class Command(BaseCommand):
    help = "Creates the 'Demir Yapı Market' demonstration organization with realistic history."

    def add_arguments(self, parser):
        parser.add_argument("--schema", default="demirmarket")
        parser.add_argument("--domain", required=True, help="Hostname that should open this organization.")
        parser.add_argument(
            "--take-over-domain",
            action="store_true",
            help="If the hostname already routes to another organization, point it here instead. "
            "The other organization and its data are left untouched.",
        )

    def handle(self, *args, **options):
        demo_password = os.environ.get("DEMO_PASSWORD")
        admin_password = os.environ.get("ADMIN_PASSWORD")
        if not demo_password or not admin_password:
            raise CommandError("Set DEMO_PASSWORD and ADMIN_PASSWORD in the environment.")

        tenant, created = Client.objects.get_or_create(
            schema_name=options["schema"], defaults={"name": COMPANY, "active_packages": ALL_PACKAGES}
        )
        self.stdout.write(f"Organization '{tenant.schema_name}': {'created' if created else 'exists'}")
        with schema_context(tenant.schema_name):
            from apps.core.models import Item

            if Item.objects.exists():
                raise CommandError(f"'{tenant.schema_name}' already has data; refusing to seed it again.")

        domain = Domain.objects.filter(domain=options["domain"]).first()
        if domain is None:
            Domain.objects.create(domain=options["domain"], tenant=tenant, is_primary=True)
        elif domain.tenant_id != tenant.id:
            if not options["take_over_domain"]:
                raise CommandError(f"{options['domain']} routes to another organization; pass --take-over-domain.")
            domain.tenant = tenant
            domain.is_primary = True
            domain.save(update_fields=["tenant", "is_primary"])
        self.stdout.write(f"Domain {options['domain']} -> {tenant.schema_name}")

        with schema_context(tenant.schema_name):
            Seeder(self.stdout, demo_password, admin_password).run()
            AuditTrail(self.stdout, tenant).run()
        self.stdout.write(self.style.SUCCESS("Demo organization ready."))


class Seeder:
    def __init__(self, stdout, demo_password, admin_password):
        self.out = stdout
        self.rng = random.Random(2026)
        self.today = timezone.localdate()
        self.demo_password = demo_password
        self.admin_password = admin_password
        self.events = []  # (datetime, order, callable)

    def say(self, message):
        self.out.write(f"  {message}")

    def schedule(self, day: date, hour: int, fn, minute: int = 0):
        """Queues `fn` to happen at that moment. Events may queue follow-ups
        (a shipment queues its payment), so this is a heap that keeps
        growing while it's drained -- not a list sorted once."""
        if day <= self.today:
            self._sequence += 1
            heapq.heappush(self.events, (datetime.combine(day, time(hour, minute)), self._sequence, fn))

    @transaction.atomic
    def run(self):
        self._sequence = 0
        self.users()
        self.master_data()
        self.plan_purchasing()
        self.plan_production()
        self.plan_sales()
        self.plan_shop()
        self.plan_people()
        # Everything happens in date order, as it would have.
        count = 0
        while self.events:
            moment, _, fn = heapq.heappop(self.events)
            with at(moment.date(), moment.hour, moment.minute):
                fn()
            count += 1
        self.say(f"{count} dated operations replayed")
        self.ledger()
        self.marketplace()
        self.reports()
        self.say("done")

    # -- users, roles -------------------------------------------------------
    def users(self):
        from apps.access import defaults
        from apps.access.models import Permission, Role
        from apps.core.models import User

        defaults.ensure_defaults()
        perms = {p.system_key: p for p in Permission.objects.filter(system_key__isnull=False)}

        def role(name, description, keys):
            r = Role.objects.create(name=name, description=description)
            r.permissions.set([perms[k] for k in keys if k in perms])
            return r

        accounting = role("Muhasebe", "Defterler, faturalar ve ödemeler.", [defaults.manage_key("general_ledger"), defaults.manage_key("receivables_payables"), defaults.view_key("inventory"), defaults.view_key("purchasing"), defaults.view_key("hr_payroll")])
        sales = role("Satış", "Potansiyel müşteriler, siparişler ve stok bilgisi.", [defaults.manage_key("sales_crm"), defaults.view_key("inventory"), defaults.view_key("item_catalog"), defaults.view_key("receivables_payables")])
        shop = role("Mağaza", "Kasa, vardiyalar ve mağaza stoğu.", [defaults.manage_key("pos"), defaults.view_key("inventory"), defaults.view_key("item_catalog")])
        admin_role = Role.objects.get(system_key=defaults.ORG_ADMIN)

        self.admin = User.objects.create_superuser(username="admin", password=self.admin_password, first_name="Sistem", last_name="Yöneticisi")
        self.ayse = User.objects.create_user(username="demo", password=self.demo_password, first_name="Ayşe", last_name="Demir", email="ayse.demir@demiryapi.example")
        admin_role.users.add(self.ayse)
        self.mehmet = User.objects.create_user(username="mehmet.kaya", password=self.demo_password, first_name="Mehmet", last_name="Kaya")
        accounting.users.add(self.mehmet)
        self.zeynep = User.objects.create_user(username="zeynep.arslan", password=self.demo_password, first_name="Zeynep", last_name="Arslan")
        sales.users.add(self.zeynep)
        self.can = User.objects.create_user(username="can.yildiz", password=self.demo_password, first_name="Can", last_name="Yıldız")
        shop.users.add(self.can)
        self.say("users and roles")

    # -- master data --------------------------------------------------------
    def master_data(self):
        from apps.core.management.commands.seed_chart_of_accounts import TEKDUZEN_SEED
        from apps.core.models import Account, Entity, Item, JournalEntry, JournalLine, Party
        from apps.inventory.models import Warehouse
        from apps.manufacturing.models import BOM, BOMLine
        from apps.pos.models import Store, Till

        self.entity = Entity.objects.create(name=COMPANY, code="DYM")
        self.entity2 = Entity.objects.create(name="Demir Yapı Lojistik Ltd. Şti.", code="DYL")
        for entity in (self.entity, self.entity2):
            Account.objects.bulk_create(Account(entity=entity, code=c, name=n, account_type=t) for c, n, t, _ in TEKDUZEN_SEED)
        self.acc = {a.code: a for a in Account.objects.filter(entity=self.entity)}
        self.acc2 = {a.code: a for a in Account.objects.filter(entity=self.entity2)}

        self.items = {}
        self.spec = {}
        for sku, name, unit, cost, price, vendor, monthly, shop in ITEMS:
            self.items[sku] = Item.objects.create(sku=sku, name=name, unit_of_measure=unit)
            # VOLUME scales the B2B trade to a size that carries 24 salaries.
            self.spec[sku] = {"cost": D(cost), "price": (D(price) * PRICE_UPLIFT).quantize(D("1")), "vendor": vendor, "monthly": int(monthly * VOLUME), "shop": shop}

        self.vendors = {}
        for key, (name, terms) in VENDORS.items():
            self.vendors[key] = Party.objects.create(entity=self.entity, name=name, party_type=Party.VENDOR, tax_id=self._tax_id(), payment_terms_days=terms, phone=self._phone())
        self.customers = []
        for name, terms, reliability, weight in CUSTOMERS:
            party = Party.objects.create(entity=self.entity, name=name, party_type=Party.CUSTOMER, tax_id=self._tax_id(), payment_terms_days=terms, phone=self._phone())
            self.customers.append((party, reliability, weight))
        Party.objects.create(entity=self.entity2, name="Demir Yapı Market A.Ş. (grup içi)", party_type=Party.BOTH, tax_id=self._tax_id())

        self.wh_main = Warehouse.objects.create(code="MRK", name="Merkez Depo — Tuzla")
        self.wh_shop = Warehouse.objects.create(code="KDK", name="Kadıköy Mağaza Deposu")
        self.wh_plant = Warehouse.objects.create(code="URT", name="Üretim Tesisi — Gebze")

        self.bom = BOM.objects.create(item=self.items[PRODUCED], name="Demir Hazır Sıva — standart reçete")
        for sku, per in BOM_COMPONENTS:
            BOMLine.objects.create(bom=self.bom, component_item=self.items[sku], quantity_per=D(per))

        self.store = Store.objects.create(entity=self.entity, warehouse=self.wh_shop, code="KDK", name="Kadıköy Mağaza")
        self.tills = [Till.objects.create(store=self.store, code="K1", name="Kasa 1"), Till.objects.create(store=self.store, code="K2", name="Kasa 2")]

        with at(START, 9):
            opening = JournalEntry.objects.create(entity=self.entity, date=START, memo="Açılış bakiyeleri", created_by=self.mehmet)
            JournalLine.objects.create(journal_entry=opening, account=self.acc["102"], debit=D("9500000"))
            JournalLine.objects.create(journal_entry=opening, account=self.acc["100"], debit=D("45000"))
            JournalLine.objects.create(journal_entry=opening, account=self.acc["500"], credit=D("9545000"))
            opening.post()
            opening2 = JournalEntry.objects.create(entity=self.entity2, date=START, memo="Açılış bakiyeleri", created_by=self.mehmet)
            JournalLine.objects.create(journal_entry=opening2, account=self.acc2["102"], debit=D("640000"))
            JournalLine.objects.create(journal_entry=opening2, account=self.acc2["500"], credit=D("640000"))
            opening2.post()
        self.say(f"master data: {len(self.items)} items, {len(self.customers)} customers, {len(self.vendors)} vendors")

    def _tax_id(self):
        return "".join(str(self.rng.randint(0, 9)) for _ in range(10))

    def _phone(self):
        return f"0 (2{self.rng.choice('1356')}{self.rng.randint(0, 9)}) {self.rng.randint(200, 899)} {self.rng.randint(10, 99)} {self.rng.randint(10, 99)}"

    def _months(self):
        month = START
        while month <= self.today:
            yield month
            month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)

    def _day_in(self, month, low=1, high=28):
        day = month.replace(day=self.rng.randint(low, high))
        while day.weekday() == 6:  # Sundays closed
            day += timedelta(days=1)
        return day

    # -- purchasing -----------------------------------------------------------
    @staticmethod
    def _growth(month):
        return 1 + 0.035 * ((month.year - START.year) * 12 + month.month - START.month)

    def _needed_per_month(self, sku):
        spec = self.spec[sku]
        units = spec["monthly"]
        if spec["shop"]:
            units += max(10, spec["monthly"] // 12) if sku != PRODUCED else 0
        for component, per in BOM_COMPONENTS:
            if component == sku:
                units += int(D(per) * 900)
        return units

    def plan_purchasing(self):
        from apps.inventory.services import get_quantity_on_hand
        from apps.purchasing.models import PurchaseOrder, PurchaseOrderLine

        by_vendor = {}
        for sku, spec in self.spec.items():
            if spec["vendor"]:
                by_vendor.setdefault(spec["vendor"], []).append(sku)

        self.pending_bills = []
        for month in self._months():
            for half, (low, high) in enumerate(((1, 4), (13, 17))):
                for vendor_key, skus in by_vendor.items():
                    order_day = self._day_in(month, low, high)
                    receive_day = order_day + timedelta(days=self.rng.randint(2, 6))
                    is_latest = order_day > self.today - timedelta(days=10)

                    def place(vendor_key=vendor_key, skus=skus, month=month, order_day=order_day, receive_day=receive_day, is_latest=is_latest):
                        # A buyer tops each item up to about a month of demand,
                        # counting what's on the shelf and what's already on order.
                        lines = []
                        for sku in skus:
                            target = D(self._needed_per_month(sku)) * D(str(self._growth(month) * self.rng.uniform(1.0, 1.15)))
                            on_order = sum(
                                (line.quantity_ordered - line.quantity_received
                                 for line in PurchaseOrderLine.objects.filter(item=self.items[sku]).exclude(purchase_order__status__in=["received", "cancelled"])),
                                D("0"),
                            )
                            need = int(target - get_quantity_on_hand(self.items[sku], self.wh_main) - on_order)
                            if need >= max(5, target * D("0.15")):
                                lines.append((sku, D(need)))
                        if not lines:
                            return
                        po = PurchaseOrder.objects.create(
                            party=self.vendors[vendor_key], warehouse=self.wh_main, order_date=order_day, expected_date=receive_day, memo="Stok ikmali"
                        )
                        for sku, qty in lines:
                            PurchaseOrderLine.objects.create(purchase_order=po, item=self.items[sku], quantity_ordered=qty, unit_price=self.spec[sku]["cost"])
                        if is_latest and self.rng.random() < 0.25:
                            return  # still a draft, waiting for someone to approve it
                        if po.requires_approval:
                            po.approve(self.ayse)
                        po.mark_sent()
                        if receive_day <= self.today and not (is_latest and self.rng.random() < 0.5):
                            self.schedule(receive_day, 11, lambda po=po: self._receive(po))

                    self.schedule(order_day, 9, place, minute=self.rng.randint(0, 50))
        self.say("purchasing planned")

    def _receive(self, po):
        from apps.core.models import Payment
        from apps.purchasing.models import PurchaseOrderLine

        lines = [{"line_id": line.id, "quantity": line.quantity_ordered - line.quantity_received} for line in PurchaseOrderLine.objects.filter(purchase_order=po)]
        bill = po.receive(lines)
        bill.mark_sent()
        pay_day = bill.due_date + timedelta(days=self.rng.randint(-5, 3))
        if pay_day <= self.today - timedelta(days=1):
            self.schedule(pay_day, 15, lambda bill=bill, pay_day=pay_day: Payment.objects.create(bill=bill, amount=bill.total, date=pay_day, method="EFT"))

    # -- production -----------------------------------------------------------
    def plan_production(self):
        from apps.inventory.models import StockMove
        from apps.inventory.services import get_quantity_on_hand
        from apps.manufacturing.models import WorkOrder

        for month in self._months():
            for start_day in (3, 17):
                day = month.replace(day=start_day)
                if day > self.today + timedelta(days=10) or (month == START and start_day == 3):
                    continue  # (the first run waits for the opening stock to arrive)
                quantity = D(self.rng.choice([400, 450, 500]))

                def transfer(quantity=quantity, day=day):
                    for sku, per in BOM_COMPONENTS:
                        units = min(D(per) * quantity, max(get_quantity_on_hand(self.items[sku], self.wh_main), D("0")))
                        if units <= 0:
                            continue
                        StockMove.objects.create(item=self.items[sku], warehouse=self.wh_main, move_type=StockMove.TRANSFER_OUT, quantity=-units, reference=f"Üretim ikmali {day}")
                        StockMove.objects.create(item=self.items[sku], warehouse=self.wh_plant, move_type=StockMove.TRANSFER_IN, quantity=units, reference=f"Üretim ikmali {day}")

                def produce(quantity=quantity, day=day):
                    wo = WorkOrder.objects.create(bom=self.bom, warehouse=self.wh_plant, quantity_planned=quantity, scheduled_date=day, memo="Rutin üretim")
                    if day > self.today:
                        return  # planned, not started
                    wo.release()
                    if day <= self.today - timedelta(days=2):
                        try:
                            wo.complete(quantity if day < self.today - timedelta(days=6) else quantity / 2)
                        except ValidationError:
                            return
                        # Finished goods go back to the main warehouse for sale.
                        StockMove.objects.create(item=self.items[PRODUCED], warehouse=self.wh_plant, move_type=StockMove.TRANSFER_OUT, quantity=-wo.quantity_completed, reference=f"WO-{wo.id}")
                        StockMove.objects.create(item=self.items[PRODUCED], warehouse=self.wh_main, move_type=StockMove.TRANSFER_IN, quantity=wo.quantity_completed, reference=f"WO-{wo.id}")

                if day <= self.today:
                    self.schedule(day - timedelta(days=1), 16, transfer)
                    self.schedule(day, 8, produce)
                else:
                    self.schedule(self.today, 8, produce)  # planned for next week; created today as a draft
        self.say("production planned")

    # -- sales ----------------------------------------------------------------
    def plan_sales(self):
        from apps.sales_crm.models import SalesOrder, SalesOrderLine

        weights = [w for _, _, w in self.customers]
        b2b = [sku for sku, spec in self.spec.items() if spec["monthly"] > 0]
        for month in self._months():
            growth = self._growth(month)
            count = int(ORDERS_PER_MONTH * growth)
            for n in range(count):
                party, reliability, _ = self.rng.choices(self.customers, weights=weights)[0]
                # Orders arrive through the month at a steady rate, not in clumps.
                low = max(2 if month == START else 1, 1 + n * 28 // count)
                day = self._day_in(month, low, max(low, (n + 1) * 28 // count))
                skus = self.rng.sample(b2b, self.rng.randint(3, 6))
                lines = []
                for sku in skus:
                    # Each order carries ~4.5 of the catalog's SKUs, so a SKU
                    # turns up in ORDERS_PER_MONTH * 4.5 / len(b2b) orders a month; size each
                    # line so those orders add up to its monthly demand.
                    share = self.spec[sku]["monthly"] * len(b2b) / (ORDERS_PER_MONTH * 4.5)
                    qty = max(5, int(share * self.rng.uniform(0.5, 1.5)))
                    price = money(self.spec[sku]["price"] * D(str(self.rng.uniform(0.93, 1.0))))
                    lines.append((sku, D(qty), price))
                ship_day = day + timedelta(days=self.rng.randint(1, 4))

                def order(party=party, reliability=reliability, day=day, ship_day=ship_day, lines=lines):
                    so = SalesOrder.objects.create(party=party, warehouse=self.wh_main, order_date=day, expected_date=ship_day + timedelta(days=1), memo="")
                    for sku, qty, price in lines:
                        SalesOrderLine.objects.create(sales_order=so, item=self.items[sku], quantity_ordered=qty, unit_price=price)
                    if day >= self.today - timedelta(days=1) and self.rng.random() < 0.4:
                        return  # just taken, not confirmed yet
                    so.confirm()
                    if ship_day <= self.today - timedelta(days=1):
                        self.schedule(ship_day, 14, lambda so=so, reliability=reliability: self._ship(so, reliability))

                self.schedule(day, 10, order, minute=self.rng.randint(0, 59))
        self.say("sales planned")

    def _ship(self, so, reliability, attempt=0):
        from apps.core.models import Payment
        from apps.inventory.services import get_quantity_on_hand
        from apps.sales_crm.models import SalesOrderLine

        lines = []
        short = False
        for line in SalesOrderLine.objects.filter(sales_order=so).select_related("item"):
            remaining = line.quantity_ordered - line.quantity_fulfilled
            quantity = min(remaining, get_quantity_on_hand(line.item, self.wh_main))
            short = short or quantity < remaining
            if quantity > 0:
                lines.append({"line_id": line.id, "quantity": quantity})
        if short and attempt < 3:
            # The rest goes out once the next delivery has landed.
            later = timezone.localdate() + timedelta(days=self.rng.randint(4, 8))
            self.schedule(later, 14, lambda: self._ship(so, reliability, attempt + 1))
        if not lines:
            return
        invoice = so.fulfill(lines)
        if invoice.issue_date >= self.today - timedelta(days=1) and self.rng.random() < 0.5:
            return  # invoiced today, not sent yet
        invoice.mark_sent()
        if self.rng.random() < reliability:
            pay_day = invoice.due_date + timedelta(days=self.rng.randint(-8, 6))
        else:
            pay_day = invoice.due_date + timedelta(days=self.rng.randint(20, 75))
        if pay_day <= self.today - timedelta(days=1):
            partial = self.rng.random() < 0.08
            amount = money(invoice.total * D("0.5")) if partial else invoice.total
            self.schedule(pay_day, 16, lambda invoice=invoice, amount=amount, pay_day=pay_day: Payment.objects.create(invoice=invoice, amount=amount, date=pay_day, method=self.rng.choice(["EFT", "Havale", "Çek"])))

    # -- shop (POS) ------------------------------------------------------------
    def plan_shop(self):
        from apps.inventory.models import StockMove
        from apps.inventory.services import get_quantity_on_hand
        from apps.pos import services
        from apps.pos.models import POSShift

        shop_skus = [sku for sku, spec in self.spec.items() if spec["shop"]]
        first_day = self.today - timedelta(days=27)

        def stock_up(day):
            for sku in shop_skus:
                # Never more than the main warehouse actually holds.
                units = min(D(self.rng.randint(25, 60)), max(get_quantity_on_hand(self.items[sku], self.wh_main) - D("20"), D("0")))
                if units <= 0:
                    continue
                StockMove.objects.create(item=self.items[sku], warehouse=self.wh_main, move_type=StockMove.TRANSFER_OUT, quantity=-units, reference=f"Mağaza sevki {day}")
                StockMove.objects.create(item=self.items[sku], warehouse=self.wh_shop, move_type=StockMove.TRANSFER_IN, quantity=units, reference=f"Mağaza sevki {day}")

        day = first_day
        while day <= self.today:
            if day.weekday() in (0, 3) or day == first_day:
                self.schedule(day, 7, lambda day=day: stock_up(day))
            if day.weekday() != 6:
                for index, till in enumerate(self.tills):
                    if index == 1 and day.weekday() not in (4, 5) and self.rng.random() < 0.5:
                        continue  # second till only on busy days
                    shift_box = {}

                    def open_shift(till=till, shift_box=shift_box):
                        shift_box["shift"] = POSShift.objects.create(till=till, opened_by=self.can, opening_cash=D("1500"))

                    self.schedule(day, 9, open_shift, minute=index * 5)
                    busy = 1.4 if day.weekday() in (4, 5) else 1.0
                    sales_today = int(self.rng.randint(9, 18) * busy)
                    last_hour = 19 if day < self.today else 15
                    for n in range(sales_today):
                        hour = self.rng.randint(9, last_hour - 1)

                        def sell(shift_box=shift_box):
                            shift = shift_box.get("shift")
                            if shift is None:
                                return
                            lines = []
                            for sku in self.rng.sample(shop_skus, self.rng.randint(1, 3)):
                                qty = D(self.rng.randint(1, 4 if self.spec[sku]["price"] < 400 else 2))
                                lines.append({"item_id": self.items[sku].id, "quantity": qty, "unit_price": self.spec[sku]["price"], "discount_amount": D("0")})
                            total = sum((line["quantity"] * line["unit_price"] for line in lines), D("0"))
                            method = "card" if self.rng.random() < 0.72 else "cash"
                            try:
                                services.checkout(shift, lines, [{"method": method, "amount": total}], self.can)
                            except ValidationError:
                                pass  # out of stock at the shop -- the customer left

                        self.schedule(day, hour, sell, minute=self.rng.randint(0, 59))
                    if day < self.today:
                        def close(shift_box=shift_box):
                            shift = shift_box.get("shift")
                            if shift is None:
                                return
                            report = shift.z_report()
                            expected = D(str(report.get("expected_cash", shift.opening_cash)))
                            shift.close(expected + self.rng.choice([D("0"), D("0"), D("-20"), D("10")]))

                        self.schedule(day, 19, close, minute=30 + index * 5)
            day += timedelta(days=1)
        self.say("shop planned")

    # -- people: HR, payroll, CRM ------------------------------------------------
    def plan_people(self):
        from apps.hr_payroll.models import Employee, LeaveRequest, PayrollRun
        from apps.sales_crm.models import Lead

        employees = []
        for first, last, position, department, hired, salary in EMPLOYEES:
            hire = date.fromisoformat(hired)
            employees.append(
                Employee.objects.create(first_name=first, last_name=last, position=position, department=department, hire_date=hire, monthly_gross_salary=D(salary), is_active=hire <= self.today, national_id=self._national_id())
            )
        self.payroll_gross = {}

        for month in self._months():
            last_day = (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            if last_day >= self.today:
                continue

            def payroll(month=month):
                # Only people on the books that month are paid.
                hired_later = [e for e in employees if e.hire_date > month.replace(day=28)]
                Employee.objects.filter(id__in=[e.id for e in hired_later]).update(is_active=False)
                run = PayrollRun.objects.create(period_year=month.year, period_month=month.month)
                run.calculate()
                run.finalize()
                self.payroll_gross[(month.year, month.month)] = sum((p.gross_salary for p in run.payslips.all()), D("0"))
                Employee.objects.filter(id__in=[e.id for e in hired_later if e.hire_date <= self.today]).update(is_active=True)

            self.schedule(last_day, 17, payroll)

        # Leave: some taken, three waiting for a decision, one turned down.
        leave_plan = [(5, -150, 5, "approved"), (12, -120, 3, "approved"), (9, -95, 10, "approved"), (14, -70, 4, "approved"), (3, -40, 5, "approved"), (17, -20, 2, "approved"), (10, -12, 1, "rejected"), (7, 9, 5, "pending"), (15, 16, 3, "pending"), (20, 30, 7, "pending")]
        for index, offset, days, status in leave_plan:
            start = self.today + timedelta(days=offset)
            requested = min(start - timedelta(days=12), self.today - timedelta(days=1))

            def leave(index=index, start=start, days=days, status=status):
                lr = LeaveRequest.objects.create(employee=employees[index], leave_type=LeaveRequest.SICK if days == 1 else LeaveRequest.ANNUAL, start_date=start, end_date=start + timedelta(days=days - 1), reason="Yıllık izin" if days > 1 else "Rapor")
                if status == "approved":
                    lr.approve()
                elif status == "rejected":
                    lr.reject()

            self.schedule(max(requested, START), 11, leave)

        statuses = [Lead.WON] * 4 + [Lead.LOST] * 4 + [Lead.QUALIFIED] * 5 + [Lead.NEW] * 5
        for name, status in zip(LEAD_NAMES, statuses):
            created = self.today - timedelta(days=self.rng.randint(1 if status == Lead.NEW else 15, 25 if status == Lead.NEW else 180))

            def lead(name=name, status=status):
                record = Lead.objects.create(name=name, status=Lead.NEW, source=self.rng.choice(LEAD_SOURCES), notes="")
                if status in (Lead.QUALIFIED, Lead.WON):
                    record.qualify()
                if status == Lead.WON:
                    record.mark_won(self.rng.choice(self.customers)[0])
                elif status == Lead.LOST:
                    record.mark_lost()

            self.schedule(created, 13, lead)
        self.say(f"{len(employees)} employees, payroll, leave and leads planned")

    def _national_id(self):
        return str(self.rng.randint(1, 9)) + "".join(str(self.rng.randint(0, 9)) for _ in range(10))

    # -- the ledger ------------------------------------------------------------
    def _weeks(self):
        """(month, first day, last day, is the month's last week) for the
        1-7, 8-14, 15-21 and 22-end stretches of each month, up to today."""
        for month in self._months():
            month_end = (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            for first, last in ((1, 7), (8, 14), (15, 21), (22, month_end.day)):
                start, end = month.replace(day=first), month.replace(day=last)
                if start > self.today:
                    break
                yield month, start, min(end, self.today), end == month_end and end <= self.today

    def ledger(self):
        """Weekly summary postings for what the subledgers don't post
        themselves: B2B sales and their cost, purchases, collections and
        vendor payments, payroll and running costs. (POS sales post their
        own entries at checkout.)"""
        from django.db.models import Sum

        from apps.core.models import Bill, Invoice, JournalEntry, JournalLine, Payment

        for month, start, end, last_of_month in self._weeks():
            # Weekly, so a month-to-date figure has a fair "same days last
            # month" to compare against.
            share = D((end - start).days + 1) / D("30")
            in_week = {"issue_date__gte": start, "issue_date__lte": end}
            sales = sum((i.total for i in Invoice.objects.filter(**in_week).exclude(status=Invoice.DRAFT).prefetch_related("lines")), D("0"))
            purchases = sum((b.total for b in Bill.objects.filter(**in_week).prefetch_related("lines")), D("0"))
            collected = Payment.objects.filter(invoice__isnull=False, date__gte=start, date__lte=end).aggregate(s=Sum("amount"))["s"] or D("0")
            paid = Payment.objects.filter(bill__isnull=False, date__gte=start, date__lte=end).aggregate(s=Sum("amount"))["s"] or D("0")
            pos_revenue = JournalLine.objects.filter(journal_entry__memo__startswith="POS sale", journal_entry__date__gte=start, journal_entry__date__lte=end, account=self.acc["600"]).aggregate(s=Sum("credit"))["s"] or D("0")
            # Salaries at month end; rent at the start of the month.
            payroll = self.payroll_gross.get((month.year, month.month), D("0")) if last_of_month else D("0")
            rent = D("95000") if start.day == 1 else D("0")
            month_end = end

            lines = [
                ("120", sales, D("0"), "Satışlar"), ("600", D("0"), sales, "Satışlar"),
                ("621", money((sales + pos_revenue) * D("0.69")), D("0"), "Satılan malın maliyeti"), ("153", D("0"), money((sales + pos_revenue) * D("0.69")), "Satılan malın maliyeti"),
                ("153", purchases, D("0"), "Alımlar"), ("320", D("0"), purchases, "Alımlar"),
                ("102", collected, D("0"), "Tahsilatlar"), ("120", D("0"), collected, "Tahsilatlar"),
                ("320", paid, D("0"), "Satıcı ödemeleri"), ("102", D("0"), paid, "Satıcı ödemeleri"),
                ("770", payroll, D("0"), "Personel giderleri"), ("102", D("0"), payroll, "Personel giderleri"),
                ("632", rent, D("0"), "Kira — Tuzla depo ve Kadıköy mağaza"), ("102", D("0"), rent, "Kira"),
                ("632", money(D(self.rng.randint(21000, 29000)) * share), D("0"), "Elektrik, su, doğalgaz"), ("102", D("0"), money(D(self.rng.randint(21000, 29000)) * share), "Faturalar"),
                ("631", money(D(self.rng.randint(18000, 42000)) * share), D("0"), "Reklam ve pazarlama"), ("102", D("0"), money(D(self.rng.randint(18000, 42000)) * share), "Reklam"),
                ("653", money(D(self.rng.randint(2500, 4800)) * share), D("0"), "Banka ve POS komisyonları"), ("102", D("0"), money(D(self.rng.randint(2500, 4800)) * share), "Komisyon"),
            ]
            # Pair each expense line with an equal bank line (the random draws
            # above differ between debit and credit; even them out).
            for i in range(12, len(lines), 2):
                code, debit, _, memo = lines[i]
                lines[i + 1] = ("102", D("0"), debit, lines[i + 1][3])
            with at(month_end, 18):
                entry = JournalEntry.objects.create(entity=self.entity, date=month_end, memo=f"{start:%d.%m}–{end:%d.%m.%Y} haftalık kayıtlar", created_by=self.mehmet)
                JournalLine.objects.bulk_create(
                    JournalLine(journal_entry=entry, account=self.acc[code], debit=debit, credit=credit, description=memo)
                    for code, debit, credit, memo in lines
                    if debit or credit
                )
                entry.post()

                # The logistics company: a small, steady business of its own.
                freight = money(D(self.rng.randint(160000, 230000)) * share)
                costs = money(freight * D(str(self.rng.uniform(0.74, 0.86))))
                entry2 = JournalEntry.objects.create(entity=self.entity2, date=month_end, memo=f"{start:%d.%m}–{end:%d.%m.%Y} haftalık kayıtlar", created_by=self.mehmet)
                for code, debit, credit in (("102", freight, 0), ("600", 0, freight), ("770", costs, 0), ("102", 0, costs)):
                    JournalLine.objects.create(journal_entry=entry2, account=self.acc2[code], debit=debit, credit=credit)
                entry2.post()

        # One draft waiting to be posted, as there always is.
        with at(self.today, 9, 20):
            draft = JournalEntry.objects.create(entity=self.entity, date=self.today, memo="Kasa sayım farkı düzeltmesi", created_by=self.mehmet)
            JournalLine.objects.create(journal_entry=draft, account=self.acc["689"], debit=D("340"))
            JournalLine.objects.create(journal_entry=draft, account=self.acc["100"], credit=D("340"))
        self.say("ledger posted")

    # -- marketplace -------------------------------------------------------------
    def marketplace(self):
        from apps.ecommerce.models import MarketplaceAccount, MarketplaceListing, MarketplaceOrder

        with at(self.today - timedelta(days=60), 10):
            account = MarketplaceAccount.objects.create(platform=MarketplaceAccount.TRENDYOL, name="Demir Yapı Market — Trendyol", entity=self.entity, warehouse=self.wh_shop, is_active=True)
        for sku in ("BOY-15", "AST-15", "FRC-01", "RLO-25", "CVD-01", "VDA-01", "MTK-01", "DRZ-05"):
            MarketplaceListing.objects.create(account=account, item=self.items[sku], external_sku=f"TY-{sku}")
        number = 418000
        for days_ago in range(29, -1, -1):
            day = self.today - timedelta(days=days_ago)
            for _ in range(self.rng.randint(2, 7)):
                number += self.rng.randint(1, 40)
                status = MarketplaceOrder.SYNCED
                error = ""
                if days_ago <= 1 and self.rng.random() < 0.4:
                    status = MarketplaceOrder.NEW
                elif self.rng.random() < 0.025:
                    status, error = MarketplaceOrder.FAILED, "Ürün eşleşmesi bulunamadı: satıcı stok kodu TY-SLK-25 kataloğda yok."
                with at(day, self.rng.randint(8, 22), self.rng.randint(0, 59)):
                    MarketplaceOrder.objects.create(account=account, external_order_id=str(number), status=status, error=error, synced_at=timezone.now() if status == MarketplaceOrder.SYNCED else None)
        account.last_synced_at = timezone.make_aware(datetime.combine(self.today, time(9, 45)))
        account.save(update_fields=["last_synced_at"])
        self.say("marketplace orders")

    def reports(self):
        from apps.bi.models import Dashboard, DashboardTile, SavedReport

        reports = [
            SavedReport.objects.create(name="Aylık gelir", series_name="monthly_revenue", chart_type=SavedReport.LINE, params={"months": 7}, owner=self.ayse, is_shared=True),
            SavedReport.objects.create(name="En büyük müşteriler", series_name="revenue_by_customer", chart_type=SavedReport.BAR, params={"top_n": 8}, owner=self.ayse, is_shared=True),
            SavedReport.objects.create(name="Tedarikçilere göre harcama", series_name="spend_by_vendor", chart_type=SavedReport.BAR, params={"top_n": 8}, owner=self.mehmet, is_shared=True),
        ]
        board = Dashboard.objects.create(name="Yönetim özeti", owner=self.ayse, is_shared=True)
        for position, report in enumerate(reports):
            DashboardTile.objects.create(dashboard=board, report=report, position=position)
        self.say("reports")


class AuditTrail:
    """A few of today's actions, performed through the API views as named
    users -- so the audit log holds genuine entries (who, when, before and
    after), each one undoable, instead of starting empty."""

    def __init__(self, stdout, tenant):
        self.out = stdout
        self.tenant = tenant

    def run(self):
        from apps.access import dispatch
        from apps.core.models import Invoice, Item, User
        from apps.hr_payroll.models import LeaveRequest
        from apps.purchasing.models import PurchaseOrder
        from apps.sales_crm.models import Lead
        from apps.sales_crm.models import SalesOrder

        today = timezone.localdate()
        users = {u.username: u for u in User.objects.all()}
        done = 0

        def act(hour, minute, username, resource, operation, **kwargs):
            nonlocal done
            with at(today, hour, minute):
                result = dispatch.perform(users[username], self.tenant, resource, operation, **kwargs)
            if result.ok:
                done += 1
            else:
                # ascii(): a Windows console can't print every Turkish letter.
                self.out.write(f"  (skipped {resource}.{operation}: {ascii(result.error[:120])})")

        draft = Invoice.objects.filter(status=Invoice.DRAFT).order_by("id").first()
        if draft:
            act(8, 42, "mehmet.kaya", "invoice", "send_document", pk=draft.id)
        po = PurchaseOrder.objects.filter(status=PurchaseOrder.DRAFT).order_by("id").first()
        if po:
            if po.requires_approval:
                act(9, 5, "demo", "purchase_order", "approve", pk=po.id)
            act(9, 12, "demo", "purchase_order", "send_document", pk=po.id)
        order = SalesOrder.objects.filter(status=SalesOrder.DRAFT).order_by("id").first()
        if order:
            act(9, 20, "zeynep.arslan", "sales_order", "confirm", pk=order.id)
        lead = Lead.objects.filter(status=Lead.NEW).order_by("id").first()
        if lead:
            act(9, 38, "zeynep.arslan", "lead", "qualify", pk=lead.id)
        open_invoice = Invoice.objects.filter(status=Invoice.SENT).order_by("due_date").first()
        if open_invoice:
            act(10, 12, "mehmet.kaya", "payment", "create", data={"invoice": open_invoice.id, "amount": str(open_invoice.balance_due.quantize(D("0.01"))), "date": str(today), "method": "EFT"})
        item = Item.objects.get(sku="BOY-15")
        act(10, 55, "demo", "item", "update", pk=item.id, data={"name": "İç Cephe Boyası 15 L Kar Beyazı"}, handler="partial_update")
        leave = LeaveRequest.objects.filter(status=LeaveRequest.PENDING).order_by("start_date").first()
        if leave:
            act(11, 20, "demo", "leave_request", "approve", pk=leave.id)
        self.out.write(f"  audit trail: {done} actions recorded")
