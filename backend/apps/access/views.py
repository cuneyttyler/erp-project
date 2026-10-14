from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import AuditLogEntry, User

from . import audit, catalog, defaults, revert
from .catalog import resource
from .models import Permission, Role
from .permissions import granted_actions, is_org_admin
from .serializers import (
    AuditLogEntrySerializer,
    PermissionSerializer,
    RoleSerializer,
    UserAdminSerializer,
)


class ActionCatalogView(APIView):
    """Every grantable action, grouped by the plugin it belongs to and then
    by resource -- what the permission editor lays out as a grid, and what
    the audit log uses to name what happened."""

    def get(self, request):
        groups: dict[str, list] = {}
        for res in catalog.grantable_resources():
            operations = [
                {"name": name, "code": res.code(name), "kind": op.kind}
                for name, op in res.operations.items()
                if name not in res.open_operations
            ]
            if operations:
                groups.setdefault(res.group, []).append({"key": res.key, "description": res.description, "operations": operations})
        return Response([{"group": group, "resources": resources} for group, resources in groups.items()])


class _SystemRecordGuard:
    """Built-in roles/permissions are kept in step with the catalog by
    defaults.ensure_defaults(); editing one by hand would just be undone."""

    def _refuse_if_system(self, instance):
        if instance.is_system:
            raise PermissionDenied("Built-in records can't be changed or deleted.")

    def list(self, request, *args, **kwargs):
        defaults.ensure_defaults()
        return super().list(request, *args, **kwargs)

    def perform_update(self, serializer):
        self._refuse_if_system(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._refuse_if_system(instance)
        instance.delete()


@resource("permission", admin_only=True, description="A named bundle of actions that can be added to roles.")
class PermissionViewSet(_SystemRecordGuard, viewsets.ModelViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    pagination_class = None


@resource("role", admin_only=True, description="A set of permissions that can be given to users.")
class RoleViewSet(_SystemRecordGuard, viewsets.ModelViewSet):
    queryset = Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    pagination_class = None


@resource("user", admin_only=True, description="The people who can sign in to this organization.")
class UserViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """No delete: a user is referenced by everything they've ever done
    (journal entries, sales, the audit trail itself). Someone who leaves is
    deactivated, which blocks sign-in and keeps that history intact."""

    queryset = User.objects.prefetch_related("roles").order_by("username")
    serializer_class = UserAdminSerializer
    pagination_class = None

    def list(self, request, *args, **kwargs):
        defaults.ensure_defaults()
        return super().list(request, *args, **kwargs)

    def perform_update(self, serializer):
        user = serializer.save()
        if user.id == self.request.user.id and not user.is_active:
            raise ValidationError({"is_active": "You can't deactivate your own account."})
        self._require_an_admin()

    def _require_an_admin(self):
        # Checked after the save, inside the request's transaction (the
        # resource mixin wraps every write in one): raising here rolls the
        # change back, whichever field it was that removed the last admin.
        admins = User.objects.filter(is_active=True).filter(Q(is_superuser=True) | Q(roles__grants_all=True))
        if not admins.exists():
            raise ValidationError("An organization must keep at least one active admin.")


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    The audit trail (REQ-CORE-AUDIT-001/004), newest first.

    An organization admin sees every entry. Anyone else sees the actions
    they took themselves, plus actions on resources they're allowed to view
    -- someone who can't open invoices can't read about them here either.
    """

    serializer_class = AuditLogEntrySerializer

    def get_queryset(self):
        user = self.request.user
        entries = AuditLogEntry.objects.select_related("user").prefetch_related("reverted_by_entries")
        if not is_org_admin(user):
            viewable = [
                res.key
                for res in catalog.grantable_resources()
                if catalog.VIEW in res.operations
                and (catalog.VIEW in res.open_operations or res.code(catalog.VIEW) in granted_actions(user))
            ]
            entries = entries.filter(Q(user=user) | Q(target_type__in=viewable))

        params = self.request.query_params
        if params.get("user"):
            entries = entries.filter(user_id=params["user"])
        if params.get("channel") in (audit.MANUAL, audit.AI):
            entries = entries.filter(channel=params["channel"])
        if params.get("resource"):
            entries = entries.filter(target_type=params["resource"])
        if params.get("action"):
            entries = entries.filter(action=params["action"])
        if params.get("date_from"):
            entries = entries.filter(created_at__date__gte=params["date_from"])
        if params.get("date_to"):
            entries = entries.filter(created_at__date__lte=params["date_to"])
        if params.get("q"):
            query = params["q"]
            entries = entries.filter(Q(target_label__icontains=query) | Q(target_id=query) | Q(action__icontains=query))
        return entries

    @action(detail=True, methods=["post"], url_path="revert")
    def revert_entry(self, request, pk=None):
        entry = self.get_object()
        try:
            created = revert.revert(entry, request.user, getattr(request, "tenant", None))
        except revert.RevertError as exc:
            return Response({"reason": exc.reason, "detail": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(created).data, status=status.HTTP_201_CREATED)
