from django.core.management.base import BaseCommand

from apps.ecommerce.models import MarketplaceAccount
from apps.ecommerce.services import push_stock_levels, sync_orders


class Command(BaseCommand):
    help = (
        "Syncs new orders and pushes current stock levels for every active "
        "marketplace account in the current tenant schema (REQ-ECOM-001/003). "
        "Manual/cron trigger until a Celery beat schedule exists -- see "
        "apps/ecommerce/tasks.py and docs/notes.md."
    )

    def handle(self, *args, **options):
        for account in MarketplaceAccount.objects.filter(is_active=True):
            orders = sync_orders(account)
            stock = push_stock_levels(account)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{account.name}: {orders['created']} order(s) synced, {orders['failed']} failed; "
                    f"{stock['pushed']} listing(s) stock-pushed, {stock['failed']} failed."
                )
            )
