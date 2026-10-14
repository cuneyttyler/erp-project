"""
The plugin catalog and the panel-widget registry.

A *plugin* is a unit of UI surface a tenant can add to or remove from the
app: the left-nav pages it contributes plus the home-panel widgets that
summarize its data. Every page in the left nav belongs to exactly one plugin
(the frontend's matching manifests live in `frontend/src/plugins/`); the
panel itself and the plugin-management page are the only two screens that
aren't removable, since removing either would leave no way back.

Two independent gates decide whether a plugin is *active* for a tenant:

- **licensed** -- the tenant's subscription includes the plugin's `package`
  (`Client.active_packages`, product.md §6.2). Core plugins have no package
  and are always licensed. This is the existing commercial gate and still
  what `HasActivePackage` enforces on each package's own API.
- **enabled** -- the tenant hasn't removed it (`PluginState`, default on).

Removing a plugin hides its pages and widgets; it deliberately does NOT block
that package's REST API or touch its data, because packages call each other
through those APIs/services (POS reads Inventory's warehouses, E-commerce
creates Sales orders) and a removed-then-re-added plugin must come back with
everything intact.

A *widget* is registered by the app that owns its data (each app's
`dashboard_widgets.py`, imported from its AppConfig.ready() -- same shape as
`ai_tools.py`), so the cross-app rule in technical.md §4 holds here too:
this app never queries another package's models itself.
"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class Plugin:
    key: str
    # The subscription package that licenses it; None = ships with Core.
    package: Optional[str]


PLUGINS: list[Plugin] = [
    Plugin("entities", None),
    Plugin("general_ledger", None),
    Plugin("receivables_payables", None),
    Plugin("item_catalog", None),
    Plugin("inventory", "inventory"),
    Plugin("purchasing", "purchasing"),
    Plugin("sales_crm", "sales_crm"),
    Plugin("manufacturing", "manufacturing"),
    Plugin("hr_payroll", "hr_payroll"),
    Plugin("pos", "pos"),
    Plugin("ecommerce", "ecommerce"),
    Plugin("bi_analytics", "bi_analytics"),
]

_PLUGINS_BY_KEY = {p.key: p for p in PLUGINS}


def get_plugin(key: str) -> Optional[Plugin]:
    return _PLUGINS_BY_KEY.get(key)


@dataclass(frozen=True)
class WidgetContext:
    user: object
    # The entity picked in the header switcher (REQ-CORE-ENT-001); None means
    # every entity together. Only GL/AR/AP widgets are entity-scoped, same as
    # the underlying models.
    entity_id: Optional[int]
    active_plugins: frozenset


# Widget kinds -- each maps to one renderer on the frontend
# (frontend/src/core/dashboard/). The payload shape per kind is documented
# on the helpers at the bottom of this module.
STAT = "stat"
CHART = "chart"
TABLE = "table"
ATTENTION = "attention"
QUICK_ACTIONS = "quick_actions"

SIZES = ("sm", "md", "lg")


@dataclass(frozen=True)
class Widget:
    key: str
    # None = a system widget, available whatever plugins are installed.
    plugin: Optional[str]
    kind: str
    size: str
    default_enabled: bool
    order: int
    func: Callable[[WidgetContext], dict]


_WIDGETS: dict[str, Widget] = {}


def register_widget(key: str, plugin: Optional[str], kind: str, order: int, size: Optional[str] = None, default_enabled: bool = True):
    """Decorator, idempotent on reload like register_metric. `order` is the
    position in the default layout (and the tiebreak for a user's own)."""
    if plugin is not None and plugin not in _PLUGINS_BY_KEY:
        raise ValueError(f"Widget '{key}' names an unknown plugin '{plugin}'.")
    default_size = {STAT: "sm", CHART: "md", TABLE: "md", ATTENTION: "md", QUICK_ACTIONS: "md"}[kind]

    def decorator(func: Callable[[WidgetContext], dict]):
        _WIDGETS[key] = Widget(
            key=key, plugin=plugin, kind=kind, size=size or default_size, default_enabled=default_enabled, order=order, func=func
        )
        return func

    return decorator


def all_widgets() -> list[Widget]:
    return sorted(_WIDGETS.values(), key=lambda w: w.order)


def get_widget(key: str) -> Optional[Widget]:
    return _WIDGETS.get(key)


# "Needs attention" providers: each app contributes the things in its own
# data that are waiting on someone, and the system `attention` widget lists
# whichever belong to an active plugin.
_ATTENTION_PROVIDERS: dict[str, tuple[Optional[str], Callable[[WidgetContext], list]]] = {}


def register_attention(plugin: Optional[str]):
    def decorator(func: Callable[[WidgetContext], list]):
        # Keyed by the function's own path so a reload replaces, not duplicates.
        _ATTENTION_PROVIDERS[f"{func.__module__}.{func.__qualname__}"] = (plugin, func)
        return func

    return decorator


def attention_providers() -> list[tuple[Optional[str], Callable[[WidgetContext], list]]]:
    return list(_ATTENTION_PROVIDERS.values())


CRITICAL = "critical"
WARNING = "warning"
INFO = "info"


def attention_item(key: str, count: int, severity: str, route: str, amount=None) -> dict:
    """One row of the needs-attention widget. `key` is translated by the
    frontend (`widgets.attentionItems.<key>`); `amount` is an optional money
    figure shown beside the count."""
    return {"key": key, "count": count, "severity": severity, "route": route, "amount": None if amount is None else str(amount)}


def stat(value, fmt: str = "money", secondary: Optional[list] = None, delta: Optional[dict] = None, trend: Optional[list] = None, route: Optional[str] = None) -> dict:
    """`fmt` is "money" or "number". `secondary` is a list of
    {"key", "value", "format"} lines under the headline; `trend` a list of
    {"label", "value"} points for the sparkline."""
    return {"value": str(value), "format": fmt, "secondary": secondary or [], "delta": delta, "trend": trend or [], "route": route}


def secondary(key: str, value, fmt: str = "number") -> dict:
    return {"key": key, "value": str(value), "format": fmt}


def delta(current, previous, compare_key: str, good_when: str = "up") -> Optional[dict]:
    """Percent change vs a named period. None when there is no previous
    figure to compare against (a percentage of zero is meaningless)."""
    if not previous:
        return None
    pct = (current - previous) / abs(previous) * 100
    return {"percent": str(round(pct, 1)), "compare_key": compare_key, "good_when": good_when}


def chart(chart_type: str, series: list, fmt: str = "money", label_kind: str = "text", route: Optional[str] = None) -> dict:
    """`chart_type` is "line", "bar" (vertical, for time/ordered buckets) or
    "hbar" (ranked categories with long names). `series` is a list of
    {"key", "points": [{"label", "value"}]} -- every series shares the same
    labels. `label_kind` tells the frontend how to print a label: "month"
    (YYYY-MM), "date" (YYYY-MM-DD), "key" (translate it) or "text"."""
    return {"chart": chart_type, "series": series, "format": fmt, "label_kind": label_kind, "route": route}


def series(key: str, points: list) -> dict:
    return {"key": key, "points": [{"label": str(label), "value": str(value)} for label, value in points]}


def table(columns: list, rows: list, route: Optional[str] = None, total_count: Optional[int] = None) -> dict:
    """`columns` is a list of (key, kind) -- kind one of "text", "money",
    "number", "date", "datetime", "status". Column headers and status values
    are translated by the frontend from their keys."""
    return {
        "columns": [{"key": key, "kind": kind} for key, kind in columns],
        "rows": rows,
        "route": route,
        "total_count": len(rows) if total_count is None else total_count,
    }
