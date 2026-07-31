import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# Plain ASGI app for now. The AI chat WebSocket/SSE routing (technical.md §6, §10.2)
# is layered in here as a ProtocolTypeRouter once apps/ai_core lands in Phase 1.
application = get_asgi_application()
