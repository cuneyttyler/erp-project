from django.apps import AppConfig


class PluginsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.plugins"
    label = "plugins"

    def ready(self):
        # The always-available panel widgets (needs-attention, quick actions)
        # -- every other widget is registered by the app that owns its data,
        # from that app's own ready().
        from . import dashboard_widgets  # noqa: F401
