"""
Advanced BI (REQ-BI-001/002/003, development-plan.md §6 Phase 3). A
`SavedReport` is one chart tile -- a saved choice of registered series
(`apps.ai_core.reporting`) plus its params and a chart type. A `Dashboard`
is an ordered collection of those tiles (REQ-BI-001's "dashboard builder").
Personal-vs-shared visibility (REQ-BI-003) mirrors `SavedView` exactly
(REQ-CORE-UX-003) -- same "owner sees their own, everyone sees shared,
edit/delete stays owner-only" shape, not a new permission model.

REQ-BI-004 (anomaly detection) is NOT modeled here -- it lives as a
computed property directly on `Bill` (apps/core/models.py) plus a
registered AI metric, since the underlying data and the anomaly check both
belong to Core's own Bill lifecycle, not a separate BI-owned record.
"""

from django.conf import settings
from django.db import models


class SavedReport(models.Model):
    BAR = "bar"
    LINE = "line"
    CHART_TYPE_CHOICES = [(BAR, "Bar"), (LINE, "Line")]

    name = models.CharField(max_length=255)
    # References a name in apps.ai_core.reporting's registry -- not a FK,
    # since the registry is in-memory/code-defined, not a DB table (same
    # relationship SavedView.config has to DataTable's column keys: a
    # string contract with a non-DB registry, validated at request time).
    series_name = models.CharField(max_length=100)
    chart_type = models.CharField(max_length=10, choices=CHART_TYPE_CHOICES, default=BAR)
    params = models.JSONField(default=dict, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_reports")
    is_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Dashboard(models.Model):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dashboards")
    is_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DashboardTile(models.Model):
    """One report placed on one dashboard, in a given position -- the
    "drag-and-drop" half of REQ-BI-001 is `position` (a plain integer the
    frontend reorders and persists via a PATCH), not literal HTML5 drag
    events modeled server-side."""

    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name="tiles")
    report = models.ForeignKey(SavedReport, on_delete=models.CASCADE, related_name="dashboard_tiles")
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["dashboard", "report"], name="unique_report_per_dashboard")
        ]

    def __str__(self) -> str:
        return f"{self.dashboard.name}: {self.report.name} (#{self.position})"
