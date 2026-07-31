from django.contrib import admin

from .models import PurchaseOrder, PurchaseOrderLine


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1
    readonly_fields = ("quantity_received",)


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "party", "warehouse", "order_date", "status", "approved_at")
    list_filter = ("status",)
    inlines = [PurchaseOrderLineInline]
    readonly_fields = ("approved_at", "approved_by")
