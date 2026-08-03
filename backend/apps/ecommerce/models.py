"""
E-commerce marketplace integration (REQ-ECOM-001/003, development-plan.md §6
Phase 3). Scope, documented once here:

- REQ-ECOM-002 (auto-generate e-Arşiv invoices for e-commerce/B2C orders) is
  NOT built -- it shares the same blocked GİB-connectivity decision every
  other Turkey compliance filing is blocked on since Phase 1 (docs/notes.md
  #1). A synced marketplace order becomes a real, confirmed SalesOrder; the
  statutory e-Arşiv document generated from it is what's missing.
- Order sync is poll-based (`services.sync_orders()` fetches "everything
  since last sync"), not webhook-driven -- a webhook receiver needs a public
  HTTPS endpoint and per-platform signature verification against a live
  store, neither of which can be built against a real store without real
  credentials (none available in this environment -- see docs/notes.md).
- `ShopifyAdapter` (adapters.py) is written against Shopify's public,
  versioned Admin REST API docs but has not been exercised against a real
  (sandbox or production) store -- treat it as a real implementation
  awaiting first live verification, not a stub.
"""

from django.db import models

from apps.core.models import Entity
from apps.inventory.models import Warehouse


class MarketplaceAccount(models.Model):
    """One connected marketplace shop/seller account (REQ-ECOM-001). Tied to
    one Entity's books and one Inventory warehouse -- same "which legal
    entity, which stock location" shape as `apps.pos.models.Store`."""

    SHOPIFY = "shopify"
    TRENDYOL = "trendyol"
    HEPSIBURADA = "hepsiburada"
    PLATFORM_CHOICES = [(SHOPIFY, "Shopify"), (TRENDYOL, "Trendyol"), (HEPSIBURADA, "Hepsiburada")]

    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    name = models.CharField(max_length=255)
    entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="marketplace_accounts")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="marketplace_accounts")
    # `shop_domain`: e.g. Shopify's "my-shop.myshopify.com". `api_secret`:
    # the platform access token/API secret -- write-only at the serializer
    # layer (never returned by the API once set). Stored as plaintext at the
    # DB level -- there's no field-level encryption or secrets-manager
    # integration in this codebase yet; a real gap, flagged in
    # docs/notes.md, not hidden.
    shop_domain = models.CharField(max_length=255, blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    api_secret = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.get_platform_display()}: {self.name}"


class MarketplaceListing(models.Model):
    """Maps one of our Items to that marketplace's own product/variant
    identifiers -- a marketplace order references its own SKU, and stock
    pushes (REQ-ECOM-003) need the platform-specific ids `push_stock_level`
    requires (e.g. Shopify's inventory_item_id + location_id), not just a
    SKU string. Deliberately manual (an admin maps a listing once), not an
    auto-discovery product-catalog importer -- see docs/notes.md."""

    account = models.ForeignKey(MarketplaceAccount, on_delete=models.CASCADE, related_name="listings")
    item = models.ForeignKey("core.Item", on_delete=models.PROTECT, related_name="marketplace_listings")
    external_sku = models.CharField(max_length=100)
    external_variant_id = models.CharField(max_length=100, blank=True)
    external_location_id = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["account", "external_sku"]
        constraints = [
            models.UniqueConstraint(fields=["account", "item"], name="unique_listing_per_account_item")
        ]

    def __str__(self) -> str:
        return f"{self.account.name}: {self.external_sku} -> {self.item.sku}"


class MarketplaceOrder(models.Model):
    """An audit/dedup record of one externally-sourced order (REQ-ECOM-001).
    `external_order_id` uniqueness per account is what makes `sync_orders()`
    safe to re-run against overlapping date ranges -- an order already
    recorded here (synced or failed) is never re-processed, only a truly new
    `external_order_id` is."""

    NEW = "new"
    SYNCED = "synced"
    FAILED = "failed"
    STATUS_CHOICES = [(NEW, "New"), (SYNCED, "Synced"), (FAILED, "Failed")]

    account = models.ForeignKey(MarketplaceAccount, on_delete=models.PROTECT, related_name="orders")
    external_order_id = models.CharField(max_length=100)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=NEW)
    sales_order = models.OneToOneField(
        "sales_crm.SalesOrder", null=True, on_delete=models.SET_NULL, related_name="marketplace_order"
    )
    error = models.TextField(blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["account", "external_order_id"], name="unique_external_order_per_account")
        ]

    def __str__(self) -> str:
        return f"{self.account.name} #{self.external_order_id} ({self.status})"
