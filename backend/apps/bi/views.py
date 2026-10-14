from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models as django_models
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai_core import reporting
from apps.core.permissions import HasActivePackage

from .models import Dashboard, DashboardTile, SavedReport
from .serializers import (
    AvailableSeriesSerializer,
    DashboardSerializer,
    DashboardTileSerializer,
    ReorderTilesSerializer,
    RunSeriesSerializer,
    SavedReportSerializer,
)
from apps.access.catalog import resource


def _active_packages(request) -> list[str]:
    tenant = getattr(request, "tenant", None)
    return tenant.active_packages if tenant else []


@resource("report_series", "bi_analytics", description="The catalog of chartable report series.")
class AvailableSeriesView(APIView):
    """REQ-BI-001: the catalog a dashboard/report builder picks from --
    only series this tenant's active_packages actually grants, same gating
    the AI chat's tool list already applies to metrics/actions."""

    permission_classes = [IsAuthenticated, HasActivePackage("bi_analytics")]

    def get(self, request):
        series = reporting.available_series(_active_packages(request))
        data = [
            {"name": s.name, "description": s.description, "input_schema": s.input_schema, "chart_kind": s.chart_kind}
            for s in series
        ]
        return Response(AvailableSeriesSerializer(data, many=True).data)


@resource("report_series_run", "bi_analytics", method_ops={"post": "view"}, description="Compute one registered report series.")
class RunSeriesView(APIView):
    """Executes a registered series by name -- never a free-form query;
    `series_name` must resolve through `reporting.get_series`, which is the
    same package-gated lookup `AvailableSeriesView` lists from."""

    permission_classes = [IsAuthenticated, HasActivePackage("bi_analytics")]

    def post(self, request):
        body = RunSeriesSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        series = reporting.get_series(body.validated_data["series_name"], _active_packages(request))
        if series is None:
            return Response({"detail": "Unknown or unavailable series."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            outcome = series.func(**body.validated_data.get("params", {}))
        except Exception as exc:
            return Response({"detail": f"Could not compute series: {exc}"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"chart_kind": series.chart_kind, "series": outcome["result"]["series"]})


@resource("saved_report", "bi_analytics")
class SavedReportViewSet(viewsets.ModelViewSet):
    """REQ-BI-001/003."""

    permission_classes = [IsAuthenticated, HasActivePackage("bi_analytics")]
    serializer_class = SavedReportSerializer

    def get_queryset(self):
        # Same ownership scoping as SavedViewViewSet -- never client-
        # filterable beyond that, so a user can't request someone else's
        # personal reports by guessing an owner id.
        return SavedReport.objects.filter(Q(owner=self.request.user) | Q(is_shared=True)).select_related("owner")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@resource("bi_dashboard", "bi_analytics", inputs={"add_tile": DashboardTileSerializer, "remove_tile": {"tile_id": "id of the tile to remove"}, "reorder_tiles": "a JSON list of {tile_id, position} objects"})
class DashboardViewSet(viewsets.ModelViewSet):
    """REQ-BI-001/003."""

    permission_classes = [IsAuthenticated, HasActivePackage("bi_analytics")]
    serializer_class = DashboardSerializer

    def get_queryset(self):
        return Dashboard.objects.filter(Q(owner=self.request.user) | Q(is_shared=True)).select_related(
            "owner"
        ).prefetch_related("tiles__report")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"], url_path="add-tile")
    def add_tile(self, request, pk=None):
        dashboard = self.get_object()
        serializer = DashboardTileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        next_position = dashboard.tiles.aggregate(max_position=django_models.Max("position"))["max_position"]
        tile = DashboardTile.objects.create(
            dashboard=dashboard,
            report=serializer.validated_data["report"],
            position=(next_position + 1) if next_position is not None else 0,
        )
        return Response(DashboardTileSerializer(tile).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="remove-tile")
    def remove_tile(self, request, pk=None):
        dashboard = self.get_object()
        tile_id = request.data.get("tile_id")
        deleted, _ = dashboard.tiles.filter(id=tile_id).delete()
        if not deleted:
            return Response({"detail": "Tile not found on this dashboard."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="reorder-tiles")
    def reorder_tiles(self, request, pk=None):
        dashboard = self.get_object()
        body = ReorderTilesSerializer(data=request.data, many=True)
        body.is_valid(raise_exception=True)
        tiles_by_id = {t.id: t for t in dashboard.tiles.all()}
        for entry in body.validated_data:
            tile = tiles_by_id.get(entry["tile_id"])
            if tile is None:
                return Response({"detail": f"Tile {entry['tile_id']} not on this dashboard."}, status=status.HTTP_400_BAD_REQUEST)
            tile.position = entry["position"]
            tile.save(update_fields=["position"])
        return Response(DashboardSerializer(dashboard).data)
