"""
Order/stock sync orchestration (REQ-ECOM-001/003). Kept separate from
adapters.py (the HTTP layer) so the ERP-side logic -- creating a SalesOrder,
matching listings, deduping by external_order_id -- is testable without
mocking requests, and the adapter is testable without a tenant schema.
"""

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import Party
from apps.inventory import services as inventory_services
from apps.sales_crm import services as sales_crm_services

from . import adapters
from .models import MarketplaceAccount, MarketplaceOrder


def _get_or_create_party(entity, email: str, name: str) -> Party:
    if not email:
        # Guest checkout with no email captured -- one shared bucket party
        # per entity rather than a Party per anonymous order, same
        # "simplify the corner case, document it" discipline as
        # Account.is_intercompany's consolidation elimination.
        party, _ = Party.objects.get_or_create(
            entity=entity, name="E-ticaret Misafir Müşteri", defaults={"party_type": Party.CUSTOMER}
        )
        return party
    party, _ = Party.objects.get_or_create(
        entity=entity, email=email, defaults={"name": name or email, "party_type": Party.CUSTOMER}
    )
    return party


def sync_orders(account: MarketplaceAccount) -> dict:
    """Fetches every new order since the account's last sync and creates a
    matching (confirmed) SalesOrder for each via sales_crm's own public
    service (technical.md §4) -- never constructs SalesOrder/SalesOrderLine
    directly. Records a MarketplaceOrder either way: `synced` on success,
    `failed` (with the reason) if a line's SKU has no active
    MarketplaceListing mapping yet, so a bad mapping surfaces as one failed
    order to go fix, not a silently dropped one."""
    if not account.is_active:
        raise ValidationError("Cannot sync a deactivated marketplace account.")

    since = account.last_synced_at or timezone.now() - timezone.timedelta(days=1)
    adapter = adapters.get_adapter(account)
    external_orders = adapter.fetch_new_orders(since)

    created, skipped, failed = 0, 0, 0
    for ext_order in external_orders:
        if MarketplaceOrder.objects.filter(account=account, external_order_id=ext_order.external_order_id).exists():
            skipped += 1
            continue

        try:
            lines = []
            for ext_line in ext_order.lines:
                listing = account.listings.select_related("item").get(external_sku=ext_line.sku, is_active=True)
                lines.append({"item": listing.item, "quantity": ext_line.quantity, "unit_price": ext_line.unit_price})
            if not lines:
                raise ValueError("Order has no lines matching an active marketplace listing.")

            party = _get_or_create_party(account.entity, ext_order.customer_email, ext_order.customer_name)
            sales_order = sales_crm_services.create_order(
                party=party,
                warehouse=account.warehouse,
                order_date=timezone.localdate(),
                lines=lines,
                memo=f"{account.get_platform_display()} #{ext_order.external_order_id}",
            )
            MarketplaceOrder.objects.create(
                account=account,
                external_order_id=ext_order.external_order_id,
                status=MarketplaceOrder.SYNCED,
                sales_order=sales_order,
                raw_payload=ext_order.raw_payload,
                synced_at=timezone.now(),
            )
            created += 1
        except Exception as exc:
            MarketplaceOrder.objects.create(
                account=account,
                external_order_id=ext_order.external_order_id,
                status=MarketplaceOrder.FAILED,
                error=str(exc),
                raw_payload=ext_order.raw_payload,
            )
            failed += 1

    account.last_synced_at = timezone.now()
    account.save(update_fields=["last_synced_at"])
    return {"created": created, "skipped": skipped, "failed": failed}


def push_stock_levels(account: MarketplaceAccount) -> dict:
    """REQ-ECOM-003: pushes current on-hand quantity for every active
    listing on this account to the marketplace, to prevent overselling.
    Independent of `sync_orders` -- stock moves from any channel (a POS
    sale, another marketplace's order, a manual adjustment) should be
    reflected here, not just this account's own orders."""
    if not account.is_active:
        raise ValidationError("Cannot push stock for a deactivated marketplace account.")

    adapter = adapters.get_adapter(account)
    pushed, failed = 0, 0
    for listing in account.listings.filter(is_active=True).select_related("item"):
        quantity = inventory_services.get_quantity_on_hand(listing.item, account.warehouse)
        try:
            adapter.push_stock_level(listing, quantity)
            pushed += 1
        except Exception:
            failed += 1
    return {"pushed": pushed, "failed": failed}
