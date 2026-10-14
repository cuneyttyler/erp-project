"""The one place audit-trail rows are written (see AuditLogEntry's docstring
in apps/core/models.py for what each field means)."""

import json
from typing import Optional

from rest_framework.renderers import JSONRenderer

from apps.core.models import AuditLogEntry

MANUAL = AuditLogEntry.MANUAL
AI = AuditLogEntry.AI

# Set on the underlying HttpRequest by dispatch.py when a request is made on
# a user's behalf from inside the server (the assistant, a revert). Never
# read from anything the browser sends, so a client can't claim a channel.
CHANNEL_ATTR = "action_channel"
REVERTS_ATTR = "audit_reverts"


def json_safe(data):
    """A snapshot as plain JSON types -- Decimals, dates and DRF's
    ReturnDicts rendered exactly as the API would send them."""
    if data is None:
        return None
    return json.loads(JSONRenderer().render(data))


def channel_of(request) -> str:
    return getattr(request, CHANNEL_ATTR, MANUAL)


def record(
    *,
    user,
    channel: str,
    action: str,
    target_type: str,
    target_id="",
    target_label: str = "",
    before=None,
    after=None,
    reverts: Optional[AuditLogEntry] = None,
) -> AuditLogEntry:
    user_id = getattr(user, "id", None)
    return AuditLogEntry.objects.create(
        actor=f"{'ai' if channel == AI else 'user'}:{user_id}",
        user=user if user_id else None,
        channel=channel,
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        target_label=(target_label or "")[:255],
        before=json_safe(before),
        after=json_safe(after),
        reverts=reverts,
    )
