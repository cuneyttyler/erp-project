from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self):
        # Registers this app's read-only AI metrics into apps.ai_core's
        # shared registry (technical.md §8.2/§8.4) -- import side-effect
        # only, mirrors Django's own signals-registration ready() pattern.
        from . import ai_tools  # noqa: F401
