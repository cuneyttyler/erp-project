from django.apps import AppConfig


class ManufacturingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.manufacturing"
    label = "manufacturing"

    def ready(self):
        from . import ai_tools  # noqa: F401
