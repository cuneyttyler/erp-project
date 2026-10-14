"""
The action catalog: every thing a user can do through the API, as a flat
list of `<resource>.<operation>` codes (`invoice.create`,
`purchase_order.approve`, `trial_balance.view`).

It is built from one declaration per API view -- the `@resource(...)`
decorator below -- and that single declaration is what four otherwise
separate features read from, so they can't drift apart:

- **Permissions** (permissions.py): a request is allowed when the user holds
  the code for the operation it performs.
- **Audit trail** (audit.py): every successful write through a declared
  resource is logged with who did it and through which channel.
- **Revert** (revert.py): a logged write is undone by performing its inverse
  through the same resource.
- **The AI assistant** (apps.ai_core.tools): it can do exactly what's in
  the catalog and nothing else, by dispatching to these same views as the
  user who's asking (dispatch.py) -- so the assistant can never be a way
  around a permission, a validation rule or the audit trail.

Nothing is listed here by hand: the operations of a resource are read off
its view (which standard CRUD handlers it has, plus its DRF `@action`s).
Adding an endpoint to a declared view adds its action to the catalog, the
permission editor and the assistant's abilities at once.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from apps.plugins.registry import get_plugin

VIEW = "view"
CREATE = "create"
UPDATE = "update"
DELETE = "delete"

READ = "read"
WRITE = "write"

# DRF's standard viewset handlers -> the operation they perform.
_STANDARD_OPS = {
    "list": VIEW,
    "retrieve": VIEW,
    "create": CREATE,
    "update": UPDATE,
    "partial_update": UPDATE,
    "destroy": DELETE,
}

# The administration area (users, roles, permissions, plugin management):
# not a plugin, and not grantable piece by piece -- see `admin_only` below.
ADMINISTRATION = "administration"


@dataclass(frozen=True)
class Operation:
    name: str
    kind: str  # READ or WRITE
    # Operates on one existing record (needs its id) vs. the collection.
    detail: bool
    # The DRF handler to dispatch to, and the HTTP method that reaches it.
    handler: str
    method: str


@dataclass
class Resource:
    key: str
    # The plugin whose pages this resource sits behind (None for the
    # administration area). Removing or lacking the plugin takes the
    # resource's actions away from everyone, whatever they've been granted.
    plugin: Optional[str]
    view: type
    description: str
    operations: dict[str, Operation]
    # handler name (or lower-case HTTP method for a plain APIView) -> operation
    handler_ops: dict[str, str]
    # Only an organization admin may use this resource at all, and its
    # actions are never offered in the permission editor. This is what
    # stops privilege escalation: nobody can be handed "edit roles" and
    # then use it to make themselves an admin.
    admin_only: bool = False
    # Operations every signed-in user holds without being granted them --
    # for reference data the whole app leans on (the company list behind the
    # header switcher). Never offered in the permission editor.
    open_operations: frozenset = frozenset()
    # operation -> compensating function for transitions that aren't plain
    # create/update/delete (see revert.py).
    revert_handlers: dict[str, Callable] = field(default_factory=dict)
    # operation -> what its request body looks like, for operations other
    # than create/update (whose body is the resource's own serializer): a
    # serializer class, or a plain description where the view reads the
    # body by hand. Only used to *describe* the action (to the assistant);
    # the view remains the one place the body is validated.
    inputs: dict = field(default_factory=dict)

    @property
    def group(self) -> str:
        return self.plugin or ADMINISTRATION

    @property
    def is_viewset(self) -> bool:
        return hasattr(self.view, "get_extra_actions")

    def code(self, operation: str) -> str:
        return f"{self.key}.{operation}"


_RESOURCES: dict[str, Resource] = {}


def _operations_of(view: type, method_ops: Optional[dict]) -> tuple[dict[str, Operation], dict[str, str]]:
    operations: dict[str, Operation] = {}
    handler_ops: dict[str, str] = {}

    def add(name: str, kind: str, detail: bool, handler: str, method: str):
        handler_ops[handler] = name
        # The first handler found for an operation is the one dispatched to
        # (`list` rather than `retrieve` for a collection-level "view").
        operations.setdefault(name, Operation(name=name, kind=kind, detail=detail, handler=handler, method=method))

    if not hasattr(view, "get_extra_actions"):
        # A plain APIView (a report): one operation per HTTP method it
        # answers. GET is "view"; anything else is named by `method_ops`.
        for method in ("get", "post", "put", "patch", "delete"):
            if not hasattr(view, method):
                continue
            name = (method_ops or {}).get(method, VIEW if method == "get" else method)
            add(name, READ if name == VIEW else WRITE, False, method, method)
        return operations, handler_ops

    standard = [("list", "get", False), ("retrieve", "get", True), ("create", "post", False), ("update", "put", True), ("partial_update", "patch", True), ("destroy", "delete", True)]
    for handler, method, detail in standard:
        if hasattr(view, handler):
            name = _STANDARD_OPS[handler]
            add(name, READ if name == VIEW else WRITE, detail and name != VIEW, handler, method)

    for extra in view.get_extra_actions():
        methods = [m.lower() for m in extra.mapping]
        if methods == ["get"]:
            # A read-only extra endpoint (a per-record report) is covered by
            # the resource's ordinary "view" permission.
            handler_ops[extra.__name__] = VIEW
            continue
        method = next(m for m in methods if m != "get")
        add(extra.__name__, WRITE, extra.detail, extra.__name__, method)
    return operations, handler_ops


def resource(
    key: str,
    plugin: Optional[str] = None,
    *,
    description: str = "",
    admin_only: bool = False,
    open_operations: tuple = (),
    method_ops: Optional[dict] = None,
    revert: Optional[dict] = None,
    inputs: Optional[dict] = None,
):
    """Declares an API view as a catalog resource.

    Returns a subclass of the view with `ResourceViewMixin` in front, so the
    one decorator line is the whole integration -- the view's own code,
    queryset and existing `permission_classes` are untouched, and the
    permission check, the audit entry and the transaction around a write all
    come from the mixin.
    """
    if plugin is not None and get_plugin(plugin) is None:
        raise ValueError(f"Resource '{key}' names an unknown plugin '{plugin}'.")

    def decorator(view: type) -> type:
        from .mixins import ResourceViewMixin

        wrapped = type(view.__name__, (ResourceViewMixin, view), {"__module__": view.__module__, "__doc__": view.__doc__})
        operations, handler_ops = _operations_of(view, method_ops)
        doc = " ".join((view.__doc__ or "").split())
        _RESOURCES[key] = wrapped.resource = Resource(
            key=key,
            plugin=plugin,
            view=wrapped,
            description=description or doc.split(". ")[0][:200],
            operations=operations,
            handler_ops=handler_ops,
            admin_only=admin_only,
            open_operations=frozenset(open_operations),
            revert_handlers=dict(revert or {}),
            inputs=dict(inputs or {}),
        )
        return wrapped

    return decorator


def _loaded() -> dict[str, Resource]:
    """Resources register as their views are imported, which a web process
    does when it first resolves a URL. A management command, shell or worker
    never does -- so import the URLconf here before answering, or half the
    catalog would be missing."""
    from django.urls import get_resolver

    get_resolver().url_patterns
    return _RESOURCES


def all_resources() -> list[Resource]:
    return list(_loaded().values())


def get_resource(key: str) -> Optional[Resource]:
    return _loaded().get(key)


def grantable_resources() -> list[Resource]:
    return [r for r in _loaded().values() if not r.admin_only]


def grantable_codes() -> set[str]:
    return {r.code(op) for r in grantable_resources() for op in r.operations if op not in r.open_operations}


def split_code(code: str) -> tuple[str, str]:
    resource_key, _, operation = code.partition(".")
    return resource_key, operation
