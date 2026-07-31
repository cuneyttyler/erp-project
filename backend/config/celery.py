import os

from celery import Celery

# technical.md §2: Celery + Redis for async/background jobs (reports, AI agents,
# compliance filing submission, migration import processing).
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("erp_platform")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
