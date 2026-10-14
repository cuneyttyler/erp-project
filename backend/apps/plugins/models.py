from django.conf import settings
from django.db import models


class PluginState(models.Model):
    """
    Whether this tenant has a plugin installed. Tenant-wide (one row per
    plugin in the tenant's own schema), not per user: adding or removing a
    plugin reshapes the app for everyone on the tenant.

    No row means "installed" -- the default -- so a plugin added to
    `registry.PLUGINS` later shows up for existing tenants without a data
    migration, and only an explicit removal is ever stored. `key` is a string
    contract with that code-defined catalog, not a FK (same relationship
    `SavedReport.series_name` has to the reporting registry).
    """

    key = models.CharField(max_length=50, unique=True)
    is_enabled = models.BooleanField(default=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.key}: {'installed' if self.is_enabled else 'removed'}"


class DashboardWidgetSetting(models.Model):
    """
    One user's choice for one home-panel widget: shown or hidden, where, and
    how wide. Per user rather than tenant-wide -- an accountant and a store
    manager want different panels -- unlike `PluginState`.

    As with `PluginState`, a missing row means "the registry default", so
    only widgets the user has actually arranged are stored.
    """

    SIZE_CHOICES = [("sm", "Small"), ("md", "Medium"), ("lg", "Large")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dashboard_widget_settings")
    widget_key = models.CharField(max_length=100)
    is_enabled = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    size = models.CharField(max_length=2, choices=SIZE_CHOICES)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["user", "widget_key"], name="unique_widget_setting_per_user"),
        ]

    def __str__(self) -> str:
        return f"{self.user}: {self.widget_key}"
