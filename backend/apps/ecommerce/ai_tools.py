"""E-commerce's read-only AI metrics (technical.md §8.2). Registered from
EcommerceConfig.ready() -- see apps/ecommerce/apps.py."""

from apps.ai_core.semantic import register_metric

from .models import MarketplaceAccount, MarketplaceOrder


@register_metric(
    name="marketplace_sync_status",
    description="Connected marketplace accounts, when each last synced, and how many orders failed to sync and still need attention.",
    input_schema={"type": "object", "properties": {}},
    package="ecommerce",
)
def marketplace_sync_status(**_kwargs) -> dict:
    accounts = []
    for account in MarketplaceAccount.objects.filter(is_active=True):
        failed_count = MarketplaceOrder.objects.filter(account=account, status=MarketplaceOrder.FAILED).count()
        accounts.append(
            {
                "name": account.name,
                "platform": account.get_platform_display(),
                "last_synced_at": account.last_synced_at.isoformat() if account.last_synced_at else None,
                "failed_order_count": failed_count,
            }
        )
    return {
        "result": {"accounts": accounts},
        "citations": [{"label": "E-Ticaret Entegrasyonları", "route": "/ecommerce/accounts"}],
    }
