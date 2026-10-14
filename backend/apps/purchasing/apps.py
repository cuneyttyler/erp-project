from django.apps import AppConfig


class PurchasingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.purchasing"
    label = "purchasing"

    def ready(self):
        from . import ai_tools  # noqa: F401
        from . import dashboard_widgets  # noqa: F401
