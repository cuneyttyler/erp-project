from rest_framework import serializers

from .models import Dashboard, DashboardTile, SavedReport


class AvailableSeriesSerializer(serializers.Serializer):
    """Describes one registered `apps.ai_core.reporting.Series` -- the
    catalog a dashboard/report builder UI picks from, same shape as the
    metrics catalog the AI chat's tool list is built from."""

    name = serializers.CharField()
    description = serializers.CharField()
    input_schema = serializers.DictField()
    chart_kind = serializers.ChoiceField(choices=["time", "category"])


class RunSeriesSerializer(serializers.Serializer):
    series_name = serializers.CharField()
    params = serializers.DictField(required=False, default=dict)


class SeriesPointSerializer(serializers.Serializer):
    label = serializers.CharField()
    value = serializers.CharField()


class SavedReportSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = SavedReport
        fields = [
            "id",
            "name",
            "series_name",
            "chart_type",
            "params",
            "owner_username",
            "is_shared",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class DashboardTileSerializer(serializers.ModelSerializer):
    report = SavedReportSerializer(read_only=True)
    report_id = serializers.PrimaryKeyRelatedField(source="report", queryset=SavedReport.objects.all(), write_only=True)

    class Meta:
        model = DashboardTile
        fields = ["id", "report", "report_id", "position"]


class DashboardSerializer(serializers.ModelSerializer):
    tiles = DashboardTileSerializer(many=True, read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = Dashboard
        fields = ["id", "name", "owner_username", "is_shared", "tiles", "created_at"]
        read_only_fields = ["created_at"]


class ReorderTilesSerializer(serializers.Serializer):
    """`[{"tile_id": int, "position": int}, ...]` -- the whole tile order
    for one dashboard, replacing prior positions in one call rather than
    N individual PATCH requests for a drag-and-drop reorder."""

    tile_id = serializers.IntegerField()
    position = serializers.IntegerField()
