from rest_framework.permissions import BasePermission

from . import catalog
from .models import UserGrant

_CACHE_ATTR = "_access_cache"


def is_org_admin(user) -> bool:
    """An organization admin: a Django superuser (how the first account on a
    tenant is bootstrapped) or anyone holding the admin role."""
    if not getattr(user, "is_authenticated", False):
        return False
    return _load(user)["is_admin"]


def granted_actions(user) -> frozenset:
    """The action codes this user has been granted through roles and direct
    grants -- before plugin availability is applied, and meaningless for an
    org admin (who holds everything; check `is_org_admin` first)."""
    return _load(user)["actions"]


def _load(user) -> dict:
    # Cached on the user object, which lives for one request -- a permission
    # change takes effect on the very next request, with no cache to bust.
    cached = getattr(user, _CACHE_ATTR, None)
    if cached is not None:
        return cached
    roles = list(user.roles.prefetch_related("permissions"))
    is_admin = bool(user.is_superuser or any(role.grants_all for role in roles))
    actions: set[str] = set()
    if not is_admin:
        for role in roles:
            for permission in role.permissions.all():
                actions.update(permission.actions or [])
        grant = UserGrant.objects.filter(user=user).first()
        if grant:
            actions.update(grant.actions or [])
    cached = {"is_admin": is_admin, "actions": frozenset(actions)}
    setattr(user, _CACHE_ATTR, cached)
    return cached


def forget(user) -> None:
    """Drops the cached answer for this user object. Only needed where one
    user object outlives a change to its grants -- the serializer that edits
    a user's roles mid-request, and tests that reuse an object across
    requests. A real request always starts from a freshly loaded user."""
    user.__dict__.pop(_CACHE_ATTR, None)


def has_action(user, code: str) -> bool:
    """Whether the user holds this action. Plugin availability is a separate
    question (see `allowed`) -- this is only about what they've been granted."""
    resource = catalog.get_resource(catalog.split_code(code)[0])
    if resource is None or not getattr(user, "is_authenticated", False):
        return False
    if is_org_admin(user) or catalog.split_code(code)[1] in resource.open_operations:
        return True
    if resource.admin_only:
        return False
    return code in granted_actions(user)


def allowed(user, tenant, code: str) -> bool:
    """Holds the action AND its plugin is active for the tenant. A removed or
    unlicensed plugin takes its actions away from everyone, admins included
    -- the same answer the left menu and the panel give."""
    from apps.plugins.services import active_plugin_keys

    resource = catalog.get_resource(catalog.split_code(code)[0])
    if resource is None:
        return False
    if resource.plugin is not None and resource.plugin not in active_plugin_keys(tenant):
        return False
    return has_action(user, code)


def effective_codes(user, tenant) -> list[str]:
    """Every action this user can actually perform right now -- what the
    frontend uses to decide which pages and buttons to offer."""
    from apps.plugins.services import active_plugin_keys

    active = active_plugin_keys(tenant)
    admin = is_org_admin(user)
    granted = granted_actions(user)
    codes = []
    for resource in catalog.all_resources():
        if resource.plugin is not None and resource.plugin not in active:
            continue
        if resource.admin_only and not admin:
            continue
        for operation in resource.operations:
            code = resource.code(operation)
            if admin or operation in resource.open_operations or code in granted:
                codes.append(code)
    return codes


class HasActionPermission(BasePermission):
    """Allows the request when the user holds the catalog action it performs.
    Added to every `@resource` view by ResourceViewMixin, after the view's
    own permission classes (authentication, package licensing)."""

    message = "You don't have permission to do this."

    def has_permission(self, request, view):
        operation = view.resource_operation()
        if operation is None:
            # Not an operation of this resource (an OPTIONS probe, a method
            # the view doesn't implement) -- nothing to guard; DRF answers
            # 405 on its own.
            return True
        return has_action(request.user, view.resource.code(operation))


class IsOrgAdmin(BasePermission):
    message = "Only an organization admin can do this."

    def has_permission(self, request, view):
        return is_org_admin(request.user)
