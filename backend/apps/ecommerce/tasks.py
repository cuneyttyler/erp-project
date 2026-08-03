"""Celery tasks for apps.ecommerce -- order/stock sync for every active
marketplace account, across every tenant. Not wired to a Celery beat
schedule yet (same "ready to be scheduled, not scheduled" state as
apps.core.tasks.ar_reconciliation_sweep_task -- see docs/notes.md)."""

from celery import shared_task
from django_tenants.utils import get_tenant_model, schema_context

from .models import MarketplaceAccount
from .services import push_stock_levels, sync_orders


@shared_task
def sync_all_marketplace_accounts() -> dict:
    Client = get_tenant_model()
    results = {}
    for tenant in Client.objects.exclude(schema_name="public"):
        with schema_context(tenant.schema_name):
            tenant_results = {}
            for account in MarketplaceAccount.objects.filter(is_active=True):
                try:
                    order_result = sync_orders(account)
                    stock_result = push_stock_levels(account)
                    tenant_results[account.name] = {"orders": order_result, "stock": stock_result}
                except Exception as exc:
                    tenant_results[account.name] = {"error": str(exc)}
            results[tenant.schema_name] = tenant_results
    return results
