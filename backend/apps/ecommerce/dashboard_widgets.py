"""E-commerce's home-panel widgets. Registered from EcommerceConfig.ready()."""

import datetime

from django.db.models import Count, Q
from django.utils import timezone

from apps.plugins import registry as r
from apps.plugins.periods import last_days

from .models import MarketplaceAccount, MarketplaceOrder


@r.register_widget("marketplace_orders", plugin="ecommerce", kind=r.STAT, order=210)
def marketplace_orders(ctx: r.WidgetContext) -> dict:
    """Marketplace orders pulled in over the last seven days."""
    days = last_days(7)
    recent = MarketplaceOrder.objects.filter(created_at__date__gte=days[0])
    per_day = dict(recent.values_list("created_at__date").annotate(n=Count("id")))
    return r.stat(
        recent.count(),
        "number",
        secondary=[
            r.secondary("failed_orders", MarketplaceOrder.objects.filter(status=MarketplaceOrder.FAILED).count()),
            r.secondary("unsynced_orders", MarketplaceOrder.objects.filter(status=MarketplaceOrder.NEW).count()),
        ],
        trend=[{"label": str(day), "value": str(per_day.get(day, 0))} for day in days],
        route="/ecommerce/orders",
    )


@r.register_widget("marketplace_accounts", plugin="ecommerce", kind=r.TABLE, order=800, default_enabled=False)
def marketplace_accounts(ctx: r.WidgetContext) -> dict:
    accounts = MarketplaceAccount.objects.annotate(
        failed_orders=Count("orders", filter=Q(orders__status=MarketplaceOrder.FAILED))
    ).order_by("name")
    rows = [
        {
            "name": account.name,
            "platform": account.platform,
            "status": "active" if account.is_active else "inactive",
            "last_synced_at": account.last_synced_at.isoformat() if account.last_synced_at else None,
            "failed_orders": account.failed_orders,
        }
        for account in accounts[:8]
    ]
    return r.table(
        [("name", "text"), ("platform", "status"), ("status", "status"), ("last_synced_at", "datetime"), ("failed_orders", "number")],
        rows,
        route="/ecommerce/accounts",
        total_count=accounts.count(),
    )


@r.register_widget("failed_marketplace_orders", plugin="ecommerce", kind=r.TABLE, order=810, default_enabled=False)
def failed_marketplace_orders(ctx: r.WidgetContext) -> dict:
    failed = MarketplaceOrder.objects.filter(status=MarketplaceOrder.FAILED).select_related("account").order_by("-created_at")
    rows = [
        {
            "account": order.account.name,
            "external_order_id": order.external_order_id,
            "created_at": order.created_at.isoformat(),
            "error": order.error,
        }
        for order in failed[:8]
    ]
    return r.table(
        [("account", "text"), ("external_order_id", "text"), ("created_at", "datetime"), ("error", "text")],
        rows,
        route="/ecommerce/orders",
        total_count=failed.count(),
    )


STALE_SYNC_HOURS = 24


@r.register_attention("ecommerce")
def _ecommerce_attention(ctx: r.WidgetContext) -> list:
    cutoff = timezone.now() - datetime.timedelta(hours=STALE_SYNC_HOURS)
    stale = MarketplaceAccount.objects.filter(is_active=True).filter(Q(last_synced_at__lt=cutoff) | Q(last_synced_at__isnull=True)).count()
    return [
        r.attention_item("failed_marketplace_orders", MarketplaceOrder.objects.filter(status=MarketplaceOrder.FAILED).count(), r.CRITICAL, "/ecommerce/orders"),
        r.attention_item("stale_marketplace_syncs", stale, r.WARNING, "/ecommerce/accounts"),
    ]


# Page charts (see apps/core/dashboard_widgets.py).
@r.register_widget("marketplace_orders_trend", plugin="ecommerce", kind=r.CHART, order=1700, default_enabled=False)
def marketplace_orders_trend(ctx: r.WidgetContext) -> dict:
    """Marketplace orders pulled per day, last two weeks: turned into sales
    orders, or failed and waiting for someone to look."""
    days = last_days(14)
    counts = {
        (row["created_at__date"], row["status"]): row["n"]
        for row in MarketplaceOrder.objects.filter(created_at__date__gte=days[0])
        .values("created_at__date", "status")
        .annotate(n=Count("id"))
    }
    return r.chart(
        "bar",
        [
            r.series("synced_orders", [(day, counts.get((day, MarketplaceOrder.SYNCED), 0)) for day in days]),
            r.series("failed_orders", [(day, counts.get((day, MarketplaceOrder.FAILED), 0)) for day in days]),
        ],
        fmt="number",
        label_kind="date",
        route="/ecommerce/orders",
    )


@r.register_widget("marketplace_orders_by_account", plugin="ecommerce", kind=r.CHART, order=1710, default_enabled=False)
def marketplace_orders_by_account(ctx: r.WidgetContext) -> dict:
    """Orders per marketplace connection over the last 30 days."""
    since = timezone.localdate() - datetime.timedelta(days=29)
    rows = (
        MarketplaceOrder.objects.filter(created_at__date__gte=since)
        .values("account__name")
        .annotate(n=Count("id"))
        .order_by("-n")[:8]
    )
    return r.chart("hbar", [r.series("orders", [(row["account__name"], row["n"]) for row in rows])], fmt="number", route="/ecommerce/orders")
