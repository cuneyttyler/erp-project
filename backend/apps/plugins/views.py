from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.access import audit
from apps.access.permissions import is_org_admin

from . import services
from .models import DashboardWidgetSetting, PluginState
from .registry import WidgetContext, get_plugin, get_widget
from .serializers import PluginToggleSerializer, WidgetLayoutSerializer


def _can_manage_plugins(user) -> bool:
    # Installing/removing a plugin reshapes the app for the whole tenant, so
    # it's limited to organization admins (apps.access).
    return is_org_admin(user)


class PluginListView(APIView):
    """The plugin catalog with this tenant's licensed/installed state."""

    def get(self, request):
        tenant = getattr(request, "tenant", None)
        return Response({"can_manage": _can_manage_plugins(request.user), "plugins": services.plugin_rows(tenant)})


class PluginDetailView(APIView):
    """Install (`is_enabled: true`) or remove (`false`) one plugin."""

    def patch(self, request, key):
        plugin = get_plugin(key)
        if plugin is None:
            return Response({"detail": "Unknown plugin."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_manage_plugins(request.user):
            return Response({"detail": "Only a tenant admin can add or remove plugins."}, status=status.HTTP_403_FORBIDDEN)
        body = PluginToggleSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        is_enabled = body.validated_data["is_enabled"]

        tenant = getattr(request, "tenant", None)
        if is_enabled and not services.is_licensed(plugin, tenant):
            return Response(
                {"detail": f"Your subscription does not include the '{plugin.package}' package."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        state, _ = PluginState.objects.get_or_create(key=key)
        if state.is_enabled != is_enabled:
            state.is_enabled = is_enabled
            state.updated_by = request.user
            state.save()
            audit.record(
                user=request.user,
                channel=audit.channel_of(request),
                action="plugin.install" if is_enabled else "plugin.remove",
                target_type="plugin",
                target_id=key,
                target_label=key,
                before={"is_enabled": not is_enabled},
                after={"is_enabled": is_enabled},
            )
        row = next(r for r in services.plugin_rows(tenant) if r["key"] == key)
        return Response(row)


class WidgetListView(APIView):
    """Every panel widget with this user's layout applied."""

    def get(self, request):
        return Response(services.widget_rows(request.user, getattr(request, "tenant", None)))


class WidgetLayoutView(APIView):
    """Replace this user's panel layout -- list order is display order."""

    def put(self, request):
        body = WidgetLayoutSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        with transaction.atomic():
            DashboardWidgetSetting.objects.filter(user=request.user).delete()
            DashboardWidgetSetting.objects.bulk_create(
                DashboardWidgetSetting(
                    user=request.user,
                    widget_key=entry["key"],
                    is_enabled=entry["is_enabled"],
                    size=entry["size"],
                    position=position,
                )
                for position, entry in enumerate(body.validated_data["widgets"])
            )
        return Response(services.widget_rows(request.user, getattr(request, "tenant", None)))


class WidgetLayoutResetView(APIView):
    """Drop this user's layout, back to the registry defaults."""

    def post(self, request):
        DashboardWidgetSetting.objects.filter(user=request.user).delete()
        return Response(services.widget_rows(request.user, getattr(request, "tenant", None)))


class WidgetDataView(APIView):
    """Computes one widget. Gated on the widget's plugin being active for
    this tenant -- never on anything the client sends -- so removing a
    plugin (or lacking its package) closes its figures here too, not just in
    the nav."""

    def get(self, request, key):
        widget = get_widget(key)
        if widget is None:
            return Response({"detail": "Unknown widget."}, status=status.HTTP_404_NOT_FOUND)
        active = services.visible_plugin_keys(request.user, getattr(request, "tenant", None))
        if not services.is_widget_available(widget, active):
            return Response({"detail": "This widget's plugin is not installed, or you can't view it."}, status=status.HTTP_403_FORBIDDEN)

        entity_id = None
        raw_entity = request.query_params.get("entity")
        if raw_entity:
            try:
                entity_id = int(raw_entity)
            except ValueError:
                return Response({"detail": "entity must be an integer id."}, status=status.HTTP_400_BAD_REQUEST)

        ctx = WidgetContext(user=request.user, entity_id=entity_id, active_plugins=active)
        return Response({"key": widget.key, "kind": widget.kind, **widget.func(ctx)})
