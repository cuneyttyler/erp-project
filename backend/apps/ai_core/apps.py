from django.apps import AppConfig


class AiCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_core"
    label = "ai_core"

    def ready(self):
        from . import dashboard_widgets  # noqa: F401
