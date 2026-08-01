"""
The semantic layer registry (technical.md §8.2, REQ-CORE-AI-002/003/009).

Each business app registers its own read-only "metrics" here via
`register_metric` -- called from that app's `ai_tools.py`, imported in its
AppConfig.ready() (mirroring how `technical.md` §8.4 describes a per-package
`ai_tools.py` for the write path; this is the same pattern for the read
path). This keeps the cross-app dependency rule intact (technical.md §4):
apps.ai_core never imports apps.purchasing/sales_crm/etc. models directly --
each package brings its own metrics to a shared registry instead of ai_core
reaching into every package.

A metric is deliberately NOT "the LLM writes a query" (§8.1 -- text-to-SQL
accuracy collapses on realistic schemas). It's a named, versioned, typed
function the LLM can only ever *call*, never compose freely -- the same
metric definition powers this chat answer and, if surfaced there later, a
dashboard tile, so "gross margin" (or here, "cash position") can't drift
between two different code paths computing it two different ways.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable, Optional


def format_money(amount) -> str:
    """Quantizes a Decimal to 2 places before an ai_tools function hands it
    to the LLM as a monetary figure. Totals computed as `quantity *
    unit_price` (two 2-decimal-place DecimalFields, e.g. PurchaseOrder.total/
    SalesOrder.total/FinancialDocument.balance_due) land at 4 decimal places
    in raw Python Decimal arithmetic -- DRF's DecimalField.to_representation
    quantizes this automatically for ordinary API responses, but ai_tools
    functions return plain dicts, not serialized responses, so they must do
    it themselves. Same bug class as the float-coercion issue documented on
    TrialBalanceRowSerializer (technical.md §8.1), a precision-formatting
    variant instead of a type-coercion one."""
    return str(Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Metric:
    name: str
    description: str
    # JSON Schema for the metric's parameters -- passed to the LLM verbatim
    # as an Anthropic tool `input_schema` (technical.md §8.4's tool-calling
    # pattern applied to the read path).
    input_schema: dict
    # None = always available (Core, ships on every tier). Otherwise the
    # package key that must be in tenant.active_packages, exactly the same
    # gate `HasActivePackage` enforces on the equivalent REST endpoint
    # (technical.md §8.5: the AI layer must not be a back door around normal
    # permission checks).
    package: Optional[str]
    # func(**params) -> {"result": <json-serializable>, "citations": [{"label": str, "route": str}]}
    func: Callable[..., dict]


_METRICS: dict[str, Metric] = {}


def register_metric(name: str, description: str, input_schema: dict, package: Optional[str] = None):
    """Decorator: registers `func` as a callable metric. Re-registering the
    same name (e.g. on Django's autoreload re-importing a module) simply
    overwrites the previous entry -- registration is idempotent by design,
    not additive."""

    def decorator(func: Callable[..., dict]) -> Callable[..., dict]:
        _METRICS[name] = Metric(name=name, description=description, input_schema=input_schema, package=package, func=func)
        return func

    return decorator


def available_metrics(active_packages: list[str]) -> list[Metric]:
    """Every metric whose package requirement the tenant actually satisfies
    -- this is what becomes the `tools` list handed to the LLM. A metric
    never even reaches the model's context if the tenant hasn't purchased
    that package, let alone gets executed."""
    active = set(active_packages or [])
    return [m for m in _METRICS.values() if m.package is None or m.package in active]


def get_metric(name: str, active_packages: list[str]) -> Optional[Metric]:
    metric = _METRICS.get(name)
    if metric is None:
        return None
    if metric.package is not None and metric.package not in (active_packages or []):
        return None
    return metric
