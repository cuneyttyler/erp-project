"""
Performs a catalog action from inside the server, on a user's behalf, by
calling the resource's own API view -- the path the assistant and revert
take instead of touching models.

Going through the view rather than around it is the point: the action gets
the view's validation, its permission check against *that user's* grants,
its transaction and its audit entry, exactly as if the user had clicked it.
There is no service account and no elevated path here to be a way around
any of those (REQ-CORE-AI-004, technical.md §8.5).
"""

from dataclasses import dataclass
from typing import Any, Optional

from django.http import Http404
from rest_framework.exceptions import APIException
from rest_framework.test import APIRequestFactory, force_authenticate

from . import audit, catalog

_factory = APIRequestFactory()


@dataclass
class Result:
    status: int
    data: Any

    @property
    def ok(self) -> bool:
        return self.status < 400

    @property
    def error(self) -> str:
        """The failure as one readable line, whatever shape DRF gave it."""
        if self.ok:
            return ""
        data = self.data
        if isinstance(data, dict) and set(data) == {"detail"}:
            return str(data["detail"])
        return str(data)


class UnknownAction(Exception):
    pass


def _build_request(user, tenant, resource, operation, pk, data, params, handler):
    if resource is None or operation not in resource.operations:
        raise UnknownAction(f"There is no action '{getattr(resource, 'key', '?')}.{operation}'.")
    op = resource.operations[operation]

    handler = handler or op.handler
    method = op.method
    if handler in ("retrieve", "list"):
        method = "get"
    elif handler == "partial_update":
        method = "patch"

    path = f"/internal/{resource.key}/" + (f"{pk}/" if pk is not None else "")
    if method == "get":
        request = _factory.get(path, params or {})
    else:
        query = ("?" + "&".join(f"{k}={v}" for k, v in params.items())) if params else ""
        request = getattr(_factory, method)(path + query, data or {}, format="json")

    # APIRequestFactory requests skip CSRF, which is right: this isn't a
    # browser request, and the caller has already authenticated the user.
    force_authenticate(request, user=user)
    request.tenant = tenant
    # The factory's default host ("testserver") isn't an allowed host, and a
    # view that builds an absolute URL -- every paginated list does, for its
    # "next" link -- would fail on it. Use one this tenant is really served at.
    host = _tenant_host(tenant)
    if host:
        request.META["HTTP_HOST"] = host
    return request, method, handler


def _tenant_host(tenant) -> Optional[str]:
    from django.conf import settings

    domain = tenant.get_primary_domain() if tenant is not None and hasattr(tenant, "get_primary_domain") else None
    if domain is not None:
        return domain.domain
    allowed = [h for h in settings.ALLOWED_HOSTS if h and h != "*"]
    return allowed[0].lstrip(".") if allowed else None


def perform(
    user,
    tenant,
    resource_key: str,
    operation: str,
    *,
    pk=None,
    data: Optional[dict] = None,
    params: Optional[dict] = None,
    channel: str = audit.MANUAL,
    reverts_id: Optional[int] = None,
    handler: Optional[str] = None,
) -> Result:
    """Runs `<resource>.<operation>` as `user`. `data` is the request body
    for a write, `params` the query string for a read. `handler` overrides
    which of the operation's handlers to use (e.g. `retrieve` instead of
    `list` for "view", `partial_update` instead of `update`)."""
    resource = catalog.get_resource(resource_key)
    request, method, handler = _build_request(user, tenant, resource, operation, pk, data, params, handler)
    setattr(request, audit.CHANNEL_ATTR, channel)
    setattr(request, audit.REVERTS_ATTR, reverts_id)

    if resource.is_viewset:
        view = resource.view.as_view({method: handler})
    else:
        view = resource.view.as_view()
    kwargs = {"pk": pk} if pk is not None else {}
    response = view(request, **kwargs)
    return Result(status=response.status_code, data=audit.json_safe(response.data) if response.data is not None else None)


@dataclass
class Check:
    """The outcome of `check()`: whether the action would be accepted, and
    what it would act on."""

    error: str = ""
    # The record as it stands (None for a create or a collection action).
    before: Optional[dict] = None
    label: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


def check(user, tenant, resource_key: str, operation: str, *, pk=None, data: Optional[dict] = None, handler: Optional[str] = None) -> Check:
    """Would this write be accepted? Runs everything the view runs *before*
    it changes anything -- authentication, the user's permission, finding
    the record, and (for create/update) the serializer's validation -- and
    then stops. Nothing is written and nothing is logged.

    This is what lets the assistant show a person a proposal that has
    already been checked, instead of one that fails after they approve it.
    A transition's own business rule (e.g. "only a draft can be sent") is
    not run here -- that lives in the handler and is only known by doing it.
    """
    resource = catalog.get_resource(resource_key)
    try:
        request, method, handler = _build_request(user, tenant, resource, operation, pk, data, None, handler)
    except UnknownAction as exc:
        return Check(error=str(exc))
    if not resource.is_viewset:
        return Check()

    # The same setup DRF's as_view()/dispatch() perform, up to but not
    # including calling the handler.
    view = resource.view()
    view.action_map = {method: handler}
    view.args, view.kwargs = (), ({"pk": pk} if pk is not None else {})
    view.format_kwarg = None
    view.request = view.initialize_request(request)
    view.headers = view.default_response_headers
    try:
        view.initial(view.request)
        outcome = Check(before=getattr(view, "_audit_before", None), label=getattr(view, "_audit_label", ""))
        if operation in (catalog.CREATE, catalog.UPDATE):
            instance = view.get_object() if pk is not None else None
            serializer = view.get_serializer(instance, data=data or {}, partial=operation == catalog.UPDATE)
            if not serializer.is_valid():
                outcome.error = str(audit.json_safe(serializer.errors))
        return outcome
    except Http404:
        return Check(error=f"No {resource_key} with id {pk} was found.")
    except APIException as exc:
        return Check(error=str(exc.detail))
