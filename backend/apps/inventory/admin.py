from django.contrib import admin

from .models import StockMove, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = ("created_at", "item", "warehouse", "move_type", "quantity", "reference")
    list_filter = ("move_type", "warehouse")

    def has_change_permission(self, request, obj=None):
        # Stock moves are an append-only ledger, same principle as
        # AuditLogEntry/posted JournalEntry -- correct a mistake with a new
        # offsetting move, not by editing history.
        return False
