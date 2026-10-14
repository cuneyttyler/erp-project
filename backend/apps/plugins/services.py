"""Resolves the code-defined catalog (registry.py) against what this tenant
has licensed/installed and what this user has arranged."""

from .models import DashboardWidgetSetting, PluginState
from .registry import PLUGINS, Plugin, Widget, all_widgets


def is_licensed(plugin: Plugin, tenant) -> bool:
    if plugin.package is None:
        return True
    return plugin.package in ((tenant.active_packages if tenant else None) or [])


def plugin_rows(tenant) -> list[dict]:
    disabled = set(PluginState.objects.filter(is_enabled=False).values_list("key", flat=True))
    widget_counts: dict[str, int] = {}
    for widget in all_widgets():
        if widget.plugin:
            widget_counts[widget.plugin] = widget_counts.get(widget.plugin, 0) + 1
    rows = []
    for plugin in PLUGINS:
        licensed = is_licensed(plugin, tenant)
        enabled = plugin.key not in disabled
        rows.append(
            {
                "key": plugin.key,
                "package": plugin.package,
                "is_licensed": licensed,
                "is_enabled": enabled,
                "is_active": licensed and enabled,
                "widget_count": widget_counts.get(plugin.key, 0),
            }
        )
    return rows


def active_plugin_keys(tenant) -> frozenset:
    return frozenset(row["key"] for row in plugin_rows(tenant) if row["is_active"])


def visible_plugin_keys(user, tenant) -> frozenset:
    """The active plugins this user can see anything in -- they hold at
    least one of its "view" actions (apps.access). A plugin's panel widgets
    summarize its data, so they follow the same rule as its pages: no view
    permission, no figures."""
    from apps.access import catalog
    from apps.access.permissions import has_action

    active = active_plugin_keys(tenant)
    return frozenset(
        resource.plugin
        for resource in catalog.grantable_resources()
        if resource.plugin in active and catalog.VIEW in resource.operations and has_action(user, resource.code(catalog.VIEW))
    )


def is_widget_available(widget: Widget, active_plugins: frozenset) -> bool:
    return widget.plugin is None or widget.plugin in active_plugins


def widget_rows(user, tenant) -> list[dict]:
    """Every registered widget merged with this user's settings, in the
    order the panel should lay them out. Widgets the user never arranged
    keep their registry order, after the ones they did."""
    active = visible_plugin_keys(user, tenant)
    settings_by_key = {s.widget_key: s for s in DashboardWidgetSetting.objects.filter(user=user)}
    rows = []
    for widget in all_widgets():
        setting = settings_by_key.get(widget.key)
        rows.append(
            {
                "key": widget.key,
                "plugin": widget.plugin,
                "kind": widget.kind,
                "default_size": widget.size,
                "size": setting.size if setting else widget.size,
                "is_enabled": setting.is_enabled if setting else widget.default_enabled,
                "is_available": is_widget_available(widget, active),
                "_sort": (0, setting.position) if setting else (1, widget.order),
            }
        )
    rows.sort(key=lambda row: row.pop("_sort"))
    return rows
