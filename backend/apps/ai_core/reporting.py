"""
The reporting-series registry (REQ-BI-001/002, development-plan.md §6 Phase
3). Mirrors `semantic.py`'s metric registry exactly, but for chartable
*series* data (grouped/time-series rows) instead of a single scalar --
same anti-metric-drift rationale (technical.md §8.1/§8.2: "every consumer
computes a figure via the same registered definition"), just extended to
cover "revenue by month" the same way `semantic.py` already covers "cash
position." A registered series is what both the self-service dashboard
builder (`apps.bi.SavedReport`, REQ-BI-001) and the AI chat's
natural-language-to-chart path (`chat.py`, REQ-BI-002) draw from -- neither
ever free-composes a query; both only ever call a registered series
function.
"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class Series:
    name: str
    description: str
    input_schema: dict
    # "time" (a period-ordered series, renders as a line) or "category" (an
    # unordered grouping, renders as a bar chart) -- the two chart forms
    # REQ-BI-001/002 actually need; a "number" single-value case is already
    # covered by the plain metric registry, not duplicated here.
    chart_kind: str
    package: Optional[str]
    # The catalog action (apps.access) a user must hold to be offered this
    # figure -- the "view" action of the data it summarizes. Without it the
    # assistant would answer "what do customers owe us" for someone who
    # can't open the receivables screens. None = no data behind it to guard.
    requires: Optional[str]
    # func(**params) -> {"series": [{"label": str, "value": str}, ...], "citations": [...]}
    func: Callable[..., dict]


_SERIES: dict[str, Series] = {}


def register_series(
    name: str, description: str, input_schema: dict, chart_kind: str, package: Optional[str] = None, requires: Optional[str] = None
):
    """Decorator, same idempotent-on-reload behavior as register_metric."""

    def decorator(func: Callable[..., dict]) -> Callable[..., dict]:
        _SERIES[name] = Series(
            name=name, description=description, input_schema=input_schema, chart_kind=chart_kind, package=package, requires=requires, func=func
        )
        return func

    return decorator


def available_series(active_packages: list[str]) -> list[Series]:
    active = set(active_packages or [])
    return [s for s in _SERIES.values() if s.package is None or s.package in active]


def get_series(name: str, active_packages: list[str]) -> Optional[Series]:
    series = _SERIES.get(name)
    if series is None:
        return None
    if series.package is not None and series.package not in (active_packages or []):
        return None
    return series
