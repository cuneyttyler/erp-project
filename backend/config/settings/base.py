"""
Base Django settings for the AI-Native ERP platform.

Architectural choices here implement docs/technical.md directly:
- Multi-tenancy: schema-per-tenant via django-tenants (technical.md §3)
- Custom, tenant-scoped User model (technical.md §5)
- DRF + drf-spectacular for the versioned public API (technical.md §6)
- Celery/Redis for async jobs, Channels/Redis for AI chat streaming (technical.md §2)
- Turkish default locale, English fully supported from day one (REQ-NFR-I18N-001)
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-secret-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# --------------------------------------------------------------------------
# Multi-tenancy (django-tenants) — technical.md §3, §4
# --------------------------------------------------------------------------
# SHARED_APPS live in the public schema (the tenant registry itself).
# TENANT_APPS are created fresh in every tenant's own schema — this is what
# gives us the isolation guarantee described in technical.md §3/§10.
SHARED_APPS = [
    "django_tenants",
    "apps.tenants",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
]

TENANT_APPS = [
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "django_filters",
    "apps.core",
    "apps.inventory",
    "apps.purchasing",
    "apps.sales_crm",
    "apps.manufacturing",
    "apps.hr_payroll",
    "apps.ai_core",
]

INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]

TENANT_MODEL = "tenants.Client"
TENANT_DOMAIN_MODEL = "tenants.Domain"

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

MIDDLEWARE = [
    # Must run first: resolves the request's tenant schema before anything else.
    "django_tenants.middleware.main.TenantMainMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------
# Database — Postgres via the django-tenants backend (technical.md §2/§3)
# --------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": env("DB_NAME", default="erp_platform"),
        "USER": env("DB_USER", default="erp"),
        "PASSWORD": env("DB_PASSWORD", default="erp"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
        # This Postgres cluster's `template1` has a recorded collation version
        # that doesn't match the OS-provided ICU library (a cluster-level
        # mismatch unrelated to this project -- see erp_platform's own
        # creation, which sidesteps it the same way). template0 is frozen at
        # initdb time and doesn't carry the stale recorded version, so the
        # test DB clones from that instead of Django's normal default.
        "TEST": {"TEMPLATE": "template0"},
    }
}

AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# i18n — Turkish is the default locale, English is fully supported (REQ-NFR-I18N-001)
# --------------------------------------------------------------------------
LANGUAGE_CODE = "tr"
LANGUAGES = [("tr", "Türkçe"), ("en", "English")]
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# DRF / API (technical.md §6)
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    # PageNumberPagination as the global default -- it works for any queryset
    # regardless of ordering field. technical.md §12 calls for cursor
    # pagination specifically on the genuinely high-volume transactional
    # tables (JournalLine, StockMove, AuditLogEntry); that's applied per-view
    # on those endpoints as they're built, not as a blanket default that would
    # break on every other resource (DRF's CursorPagination needs a `created`
    # field our models don't uniformly have).
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "AI-Native ERP API",
    "DESCRIPTION": "Versioned REST API — see docs/technical.md §6 for design principles.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS", default=["http://localhost:5173"]
)
CORS_ALLOW_CREDENTIALS = True

# The Vite dev proxy (frontend/vite.config.ts) forwards /api/* with the Host
# header rewritten to this backend -- but the browser's own Origin header
# still says http://localhost:5173, which Django's CSRF Origin check would
# otherwise reject as cross-origin. Trusting it here is what makes the
# dev-proxy setup work at all.
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS", default=["http://localhost:5173"]
)

# --------------------------------------------------------------------------
# AI Chat Layer — LLM gateway (technical.md §8.8)
# --------------------------------------------------------------------------
# Blank by default: apps.ai_core.llm_gateway.is_configured() checks this and
# the ChatView degrades gracefully (REQ-CORE-AI-009) rather than erroring
# when it's unset -- see docs/notes.md for what needs to be supplied to
# activate the assistant.
AI_LLM_API_KEY = env("ANTHROPIC_API_KEY", default="")
AI_LLM_MODEL = env("AI_LLM_MODEL", default="claude-sonnet-5")

# --------------------------------------------------------------------------
# Celery — async jobs (technical.md §2)
# --------------------------------------------------------------------------
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# --------------------------------------------------------------------------
# Channels — AI chat streaming transport (technical.md §2, §10.2)
# --------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("REDIS_URL", default="redis://localhost:6379/0")]},
    }
}
