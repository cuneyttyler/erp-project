"""
The write/action registry (technical.md §8.4, REQ-CORE-AI-007/010).

Mirrors semantic.py's read-only metric registry exactly, but for mutating
actions: each business app registers its own typed, schema-validated write
tools here via `register_action` (from the same `ai_tools.py` a metric is
registered from -- one file per package, both registries). An action is
never executed directly from the tool-calling loop the way a metric is --
`chat.py` always wraps it in a `PendingApproval` first (see models.py) and
only `PendingApproval.approve()` actually calls `Action.func`. That's what
makes REQ-CORE-AI-007's "clear preview and explicit user confirmation"
structurally true rather than a prompt-engineering promise the model could
ignore.

Every action function re-runs the same validation/authorization the
equivalent REST endpoint would (technical.md §8.4: "a thin wrapper around
the same service-layer call the API view uses, not a separate code path")
-- see hr_payroll/ai_tools.py's `approve_leave_request` action for the
clearest example, which just calls the same `LeaveRequest.approve()` model
method the API view's `approve` action calls.
"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class Action:
    name: str
    description: str
    input_schema: dict
    package: Optional[str]
    # func(user, **params) -> {"result": <json-serializable>, "summary": str}
    # Only ever called from PendingApproval.approve() -- never from the
    # chat loop directly, and never for a preview.
    func: Callable[..., dict]
    # preview(**params) -> str: a *read-only* human-readable description of
    # what `func` would do, shown in the approval UI before anyone commits
    # to it (REQ-CORE-AI-007's "clear preview"). May safely read the
    # database (e.g. look up an employee's name) but must never write.
    # Falls back to a generic param dump if an action doesn't provide one.
    preview: Optional[Callable[..., str]] = None


_ACTIONS: dict[str, Action] = {}


def register_action(
    name: str, description: str, input_schema: dict, package: Optional[str] = None, preview: Optional[Callable] = None
):
    """Decorator, same idempotent-on-reload behavior as register_metric."""

    def decorator(func: Callable[..., dict]) -> Callable[..., dict]:
        _ACTIONS[name] = Action(
            name=name, description=description, input_schema=input_schema, package=package, func=func, preview=preview
        )
        return func

    return decorator


def default_preview(action: Action, params: dict) -> str:
    """Fallback preview for an action that didn't register its own --
    plain but honest: exactly the parameters that will be passed to it."""
    return f"{action.description} (parametreler: {params})"


def available_actions(active_packages: list[str]) -> list[Action]:
    active = set(active_packages or [])
    return [a for a in _ACTIONS.values() if a.package is None or a.package in active]


def get_action(name: str, active_packages: list[str]) -> Optional[Action]:
    action = _ACTIONS.get(name)
    if action is None:
        return None
    if action.package is not None and action.package not in (active_packages or []):
        return None
    return action
