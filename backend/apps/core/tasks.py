"""
Celery tasks for apps.core. Currently just the reconciliation sweep agent
(see agents.py's module docstring for what "agentic preview" does and
doesn't mean yet).
"""

from celery import shared_task
from django_tenants.utils import get_tenant_model, schema_context

from .agents import run_ar_reconciliation_sweep


@shared_task
def ar_reconciliation_sweep_task(threshold_days: int = 30) -> dict:
    """
    Not wired to a Celery beat schedule yet (see docs/notes.md) -- trigger
    manually with `celery_app.send_task('apps.core.tasks.ar_reconciliation_sweep_task')`
    or `manage.py run_reconciliation_sweep` until a beat entry exists.

    Iterates every tenant schema explicitly: a Celery worker has no
    implicit "current tenant" the way an HTTP request does (that's
    resolved per-request by TenantMainMiddleware, which never runs here).
    """
    Client = get_tenant_model()
    results = {}
    for tenant in Client.objects.exclude(schema_name="public"):
        with schema_context(tenant.schema_name):
            results[tenant.schema_name] = run_ar_reconciliation_sweep(threshold_days=threshold_days)
    return results
