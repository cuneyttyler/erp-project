from django.contrib import admin

from .models import Lead, SalesOrder, SalesOrderLine


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "party", "status", "source", "created_at")
    list_filter = ("status",)


class SalesOrderLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 1
    readonly_fields = ("quantity_fulfilled",)


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "party", "warehouse", "order_date", "status")
    list_filter = ("status",)
    inlines = [SalesOrderLineInline]
