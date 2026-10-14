"""The system panel widgets -- available whatever plugins are installed.
Registered from PluginsConfig.ready()."""

from .registry import ATTENTION, CRITICAL, QUICK_ACTIONS, WARNING, WidgetContext, attention_providers, register_widget

_SEVERITY_ORDER = {CRITICAL: 0, WARNING: 1}


@register_widget("attention", plugin=None, kind=ATTENTION, order=250)
def attention(ctx: WidgetContext) -> dict:
    """Everything across the installed plugins that's waiting on someone,
    most severe first. Items with nothing to report are dropped, so an empty
    list genuinely means "all clear"."""
    items = []
    for plugin, provider in attention_providers():
        if plugin is not None and plugin not in ctx.active_plugins:
            continue
        items.extend(item for item in provider(ctx) if item["count"] > 0)
    items.sort(key=lambda item: _SEVERITY_ORDER.get(item["severity"], 2))
    return {"items": items}


@register_widget("quick_actions", plugin=None, kind=QUICK_ACTIONS, order=950, size="lg")
def quick_actions(ctx: WidgetContext) -> dict:
    # Rendered entirely from the frontend's plugin manifests (it's a list of
    # links to the installed plugins' pages) -- there's no data to compute.
    return {}
