"""Production settings: everything in base.py, with the dev conveniences
removed and the values that must differ per deployment required from the
environment instead of defaulted (see infra/deploy/README.md)."""

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = False

# No fallbacks: starting with base.py's dev secret key or an open host list
# would be a silent misconfiguration, so a missing value fails at startup.
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# The browser talks to the reverse proxy (Caddy) over HTTPS; Django sees
# plain HTTP from it, with the original scheme in X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_CONTENT_TYPE_NOSNIFF = True

# The SPA is served from the same origin as the API, so only that origin
# needs trusting (base.py's list is for the Vite dev server and tunnels).
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=CSRF_TRUSTED_ORIGINS)

# Collected on container start into a volume the web server serves at
# /static/ (the Django admin and the API docs are the only users).
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
