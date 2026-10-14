"""The AI layer's home-panel widgets. The assistant ships with Core rather
than as a removable plugin (it has no left-nav page of its own), so these
are registered with `plugin=None` -- available on every tenant. Registered
from AiCoreConfig.ready()."""

from django.db.models import Count, Sum
from django.utils import timezone

from apps.access.permissions import is_org_admin
from apps.plugins import registry as r
from apps.plugins.periods import last_days

from .models import AIUsageRecord, PendingApproval


def _pending_approvals(ctx: r.WidgetContext):
    """An admin sees every open proposal; anyone else the ones they asked
    for. (The approvals API also shows a user proposals they could carry
    out for someone else -- kept out of this count so a panel figure never
    depends on a per-row permission check.)"""
    pending = PendingApproval.objects.filter(status=PendingApproval.PENDING)
    return pending if is_org_admin(ctx.user) else pending.filter(requested_by=ctx.user)


@r.register_widget("ai_pending_approvals", plugin=None, kind=r.TABLE, order=900)
def ai_pending_approvals(ctx: r.WidgetContext) -> dict:
    """Write actions the assistant has proposed that are still waiting for
    a human to approve or reject them."""
    pending = _pending_approvals(ctx).select_related("requested_by").order_by("-created_at")
    rows = [
        {
            "summary": approval.summary,
            "requested_by": approval.requested_by.username if approval.requested_by else "",
            "created_at": approval.created_at.isoformat(),
        }
        for approval in pending[:8]
    ]
    return r.table(
        [("summary", "text"), ("requested_by", "text"), ("created_at", "datetime")],
        rows,
        total_count=pending.count(),
    )


@r.register_widget("ai_usage", plugin=None, kind=r.STAT, order=230, default_enabled=False)
def ai_usage(ctx: r.WidgetContext) -> dict:
    """Assistant requests this calendar month (the metered figure behind
    REQ-CORE-AI-011): the whole organization's for an admin, their own for
    anyone else."""
    today = timezone.localdate()
    records = AIUsageRecord.objects.all() if is_org_admin(ctx.user) else AIUsageRecord.objects.filter(user=ctx.user)
    this_month = records.filter(created_at__year=today.year, created_at__month=today.month)
    tokens = this_month.aggregate(input=Sum("input_tokens"), output=Sum("output_tokens"))
    days = last_days(14)
    per_day = dict(records.filter(created_at__date__gte=days[0]).values_list("created_at__date").annotate(n=Count("id")))
    return r.stat(
        this_month.count(),
        "number",
        secondary=[
            r.secondary("input_tokens", tokens["input"] or 0),
            r.secondary("output_tokens", tokens["output"] or 0),
        ],
        trend=[{"label": str(day), "value": str(per_day.get(day, 0))} for day in days],
    )


@r.register_attention(None)
def _ai_attention(ctx: r.WidgetContext) -> list:
    return [r.attention_item("ai_pending_approvals", _pending_approvals(ctx).count(), r.WARNING, "/assistant")]
