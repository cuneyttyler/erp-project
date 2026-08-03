from django.contrib import admin

from .models import MarketplaceAccount, MarketplaceListing, MarketplaceOrder


@admin.register(MarketplaceAccount)
class MarketplaceAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "platform", "entity", "warehouse", "is_active", "last_synced_at")
    list_filter = ("platform", "is_active")


@admin.register(MarketplaceListing)
class MarketplaceListingAdmin(admin.ModelAdmin):
    list_display = ("account", "external_sku", "item", "is_active")
    list_filter = ("is_active",)


@admin.register(MarketplaceOrder)
class MarketplaceOrderAdmin(admin.ModelAdmin):
    list_display = ("account", "external_order_id", "status", "sales_order", "created_at")
    list_filter = ("status",)
