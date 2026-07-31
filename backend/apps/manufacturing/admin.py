from django.contrib import admin

from .models import BOM, BOMLine, WorkOrder


class BOMLineInline(admin.TabularInline):
    model = BOMLine
    extra = 1


@admin.register(BOM)
class BOMAdmin(admin.ModelAdmin):
    list_display = ("item", "name", "is_active")
    list_filter = ("is_active",)
    inlines = [BOMLineInline]


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "bom", "warehouse", "quantity_planned", "quantity_completed", "status", "scheduled_date")
    list_filter = ("status",)
    readonly_fields = ("quantity_completed",)
