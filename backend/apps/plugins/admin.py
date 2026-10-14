from django.contrib import admin

from .models import DashboardWidgetSetting, PluginState


@admin.register(PluginState)
class PluginStateAdmin(admin.ModelAdmin):
    list_display = ["key", "is_enabled", "updated_by", "updated_at"]


@admin.register(DashboardWidgetSetting)
class DashboardWidgetSettingAdmin(admin.ModelAdmin):
    list_display = ["user", "widget_key", "is_enabled", "position", "size"]
    list_filter = ["user"]
