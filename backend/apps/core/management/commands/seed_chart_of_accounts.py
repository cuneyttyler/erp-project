from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Account

# A representative starting subset of the Turkish Tekdüzen Hesap Planı
# (Uniform Chart of Accounts), grouped by the standard 1-7 class structure.
# This is intentionally NOT the full ~300-account statutory plan -- it's
# enough for a real small business's first books and a template a tenant
# can extend. Codes/names follow the standard numbering so anything added
# later slots in at the right place.
#
# (code, name, account_type, parent_code)
TEKDUZEN_SEED = [
    # 1 - Dönen Varlıklar (Current Assets)
    ("100", "Kasa", Account.ASSET, None),
    ("102", "Bankalar", Account.ASSET, None),
    ("120", "Alıcılar", Account.ASSET, None),
    ("128", "Şüpheli Ticari Alacaklar", Account.ASSET, None),
    ("153", "Ticari Mallar", Account.ASSET, None),
    ("191", "İndirilecek KDV", Account.ASSET, None),
    ("193", "Peşin Ödenen Vergiler ve Fonlar", Account.ASSET, None),
    # 2 - Duran Varlıklar (Fixed Assets)
    ("253", "Tesis, Makine ve Cihazlar", Account.ASSET, None),
    ("255", "Demirbaşlar", Account.ASSET, None),
    ("257", "Birikmiş Amortismanlar (-)", Account.ASSET, None),
    ("260", "Haklar", Account.ASSET, None),
    # 3 - Kısa Vadeli Yabancı Kaynaklar (Current Liabilities)
    ("300", "Banka Kredileri", Account.LIABILITY, None),
    ("320", "Satıcılar", Account.LIABILITY, None),
    ("335", "Personele Borçlar", Account.LIABILITY, None),
    ("360", "Ödenecek Vergi ve Fonlar", Account.LIABILITY, None),
    ("361", "Ödenecek Sosyal Güvenlik Kesintileri", Account.LIABILITY, None),
    ("391", "Hesaplanan KDV", Account.LIABILITY, None),
    # 4 - Uzun Vadeli Yabancı Kaynaklar (Long-Term Liabilities)
    ("400", "Banka Kredileri (Uzun Vadeli)", Account.LIABILITY, None),
    ("480", "Gelecek Yıllara Ait Gelirler", Account.LIABILITY, None),
    # 5 - Özkaynaklar (Equity)
    ("500", "Sermaye", Account.EQUITY, None),
    ("570", "Geçmiş Yıllar Kârları", Account.EQUITY, None),
    ("580", "Geçmiş Yıllar Zararları (-)", Account.EQUITY, None),
    ("590", "Dönem Net Kârı", Account.EQUITY, None),
    # 6 - Gelir Tablosu Hesapları (Income Statement — Revenue/COGS/Expense)
    ("600", "Yurtiçi Satışlar", Account.REVENUE, None),
    ("601", "Yurtdışı Satışlar", Account.REVENUE, None),
    ("610", "Satıştan İadeler (-)", Account.REVENUE, None),
    ("611", "Satış İskontoları (-)", Account.REVENUE, None),
    ("620", "Satılan Mamuller Maliyeti", Account.EXPENSE, None),
    ("621", "Satılan Ticari Mallar Maliyeti", Account.EXPENSE, None),
    ("631", "Pazarlama Satış ve Dağıtım Giderleri", Account.EXPENSE, None),
    ("632", "Genel Yönetim Giderleri", Account.EXPENSE, None),
    ("653", "Komisyon Giderleri", Account.EXPENSE, None),
    ("656", "Kambiyo Zararları", Account.EXPENSE, None),
    ("660", "Kısa Vadeli Borçlanma Giderleri", Account.EXPENSE, None),
    ("679", "Diğer Olağandışı Gelir ve Kârlar", Account.REVENUE, None),
    ("689", "Diğer Olağandışı Gider ve Zararlar", Account.EXPENSE, None),
    ("690", "Dönem Kârı veya Zararı", Account.EQUITY, None),
    ("770", "Genel Yönetim Giderleri", Account.EXPENSE, None),
]


class Command(BaseCommand):
    help = (
        "Seeds the current tenant schema's Chart of Accounts with a starter "
        "Turkish Tekdüzen Hesap Planı subset (REQ-CORE-GL-001). Idempotent -- "
        "safe to re-run; existing codes are left untouched."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        for code, name, account_type, _parent_code in TEKDUZEN_SEED:
            _, created = Account.objects.get_or_create(
                code=code, defaults={"name": name, "account_type": account_type}
            )
            if created:
                created_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded chart of accounts: {created_count} created, "
                f"{len(TEKDUZEN_SEED) - created_count} already existed."
            )
        )
