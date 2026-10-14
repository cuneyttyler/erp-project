from django.contrib import admin

from .models import Dashboard, DashboardTile, SavedReport


class DashboardTileInline(admin.TabularInline):
    model = DashboardTile
    extra = 0


@admin.register(SavedReport)
class SavedReportAdmin(admin.ModelAdmin):
    list_display = ("name", "series_name", "chart_type", "owner", "is_shared")
    list_filter = ("chart_type", "is_shared")


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_shared")
    list_filter = ("is_shared",)
    inlines = [DashboardTileInline]
