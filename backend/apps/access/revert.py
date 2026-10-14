"""
Undoing a logged action.

A revert never rewrites history. It performs the *inverse* action through
the same resource view (dispatch.py), which validates it, checks the
reverting user's own permissions and logs it as a new audit entry pointing
back at the one it undoes.

- a **create** is undone by deleting the record;
- an **update** by writing the "before" snapshot back;
- a **delete** by creating the record again from its "before" snapshot (it
  comes back with a new id -- anything that pointed at the old id is not
  re-linked);
- any other operation (posting, sending, approving...) only if its resource
  declared a compensating handler for it in `@resource(revert={...})`. Where
  it didn't, that's deliberate: receiving goods, fulfilling an order or
  ringing up a sale move stock and money in ways that have their own proper
  business reversal (a return, a credit note), not a silent undo.

An entry can only be reverted while it is the latest change to its record --
otherwise undoing it would silently discard whatever was done since. Revert
the later changes first.
"""

from typing import Callable, Optional

from django.db import transaction

from apps.core.models import AuditLogEntry

from . import audit, catalog, dispatch
from .permissions import has_action


class RevertError(Exception):
    """Carries a machine-readable reason (translated by the frontend) and a
    human-readable detail."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail


def _blocker(entry: AuditLogEntry, user) -> Optional[str]:
    """Why this entry can't be reverted by this user, or None if it can."""
    resource = catalog.get_resource(entry.target_type)
    resource_key, operation = catalog.split_code(entry.action)
    if resource is None or resource_key != entry.target_type or operation not in resource.operations:
        return "not_an_action"  # an AI conversation log, a plugin toggle, ...
    if entry.reverts_id is not None:
        return "is_a_revert"
    if entry.reverted_by_entries.exists():
        return "already_reverted"
    if operation not in (catalog.CREATE, catalog.UPDATE, catalog.DELETE) and operation not in resource.revert_handlers:
        return "not_reversible"
    if operation in (catalog.CREATE, catalog.UPDATE, catalog.DELETE) and _inverse(resource, operation) is None:
        return "not_reversible"
    if not entry.target_id:
        return "not_reversible"
    if not has_action(user, entry.action):
        return "no_permission"
    # Later changes that have themselves been undone (and the entries that
    # undid them) cancel out -- only a later change still in effect blocks.
    later = AuditLogEntry.objects.filter(
        target_type=entry.target_type,
        target_id=entry.target_id,
        id__gt=entry.id,
        reverts__isnull=True,
        reverted_by_entries__isnull=True,
    )
    if later.exists():
        return "changed_since"
    return None


def _inverse(resource: catalog.Resource, operation: str) -> Optional[str]:
    inverse = {catalog.CREATE: catalog.DELETE, catalog.UPDATE: catalog.UPDATE, catalog.DELETE: catalog.CREATE}[operation]
    return inverse if inverse in resource.operations else None


def status(entry: AuditLogEntry, user) -> dict:
    blocker = _blocker(entry, user)
    return {"can_revert": blocker is None, "reason": blocker}


def revert(entry: AuditLogEntry, user, tenant, channel: str = audit.MANUAL) -> AuditLogEntry:
    blocker = _blocker(entry, user)
    if blocker is not None:
        raise RevertError(blocker)

    resource = catalog.get_resource(entry.target_type)
    _, operation = catalog.split_code(entry.action)

    handler = resource.revert_handlers.get(operation)
    if handler is not None:
        # A compensating handler does its own work and logs its own entry;
        # one transaction, so it can't do the first without the second.
        with transaction.atomic():
            handler(entry, user, tenant, channel)
    elif operation == catalog.CREATE:
        _check(dispatch.perform(user, tenant, resource.key, catalog.DELETE, pk=entry.target_id, channel=channel, reverts_id=entry.id))
    elif operation == catalog.UPDATE:
        _check(dispatch.perform(user, tenant, resource.key, catalog.UPDATE, pk=entry.target_id, data=entry.before, channel=channel, reverts_id=entry.id, handler="partial_update"))
    else:
        _check(dispatch.perform(user, tenant, resource.key, catalog.CREATE, data=entry.before, channel=channel, reverts_id=entry.id))

    created = entry.reverted_by_entries.order_by("-id").first()
    if created is None:
        raise RevertError("failed", "The inverse action ran but left no audit entry.")
    return created


def _check(result: dispatch.Result):
    if not result.ok:
        raise RevertError("failed", result.error)


# -- compensating handlers --------------------------------------------------
def restore_fields(*fields: str) -> Callable:
    """A compensating handler for a transition that only changed a few
    columns on the record itself (a status, an approval stamp): puts those
    columns back to what the entry's "before" snapshot says. Not for
    transitions with side effects elsewhere -- those must not be declared
    revertible this way."""

    def handler(entry: AuditLogEntry, user, tenant, channel: str):
        resource = catalog.get_resource(entry.target_type)
        model = resource.view.queryset.model
        instance = model._default_manager.filter(pk=entry.target_id).first()
        if instance is None:
            raise RevertError("failed", "The record no longer exists.")
        before_now = _snapshot(resource, instance)
        for name in fields:
            # `attname` so a related record is restored from the id the
            # snapshot holds it as.
            setattr(instance, model._meta.get_field(name).attname, (entry.before or {}).get(name))
        instance.save(update_fields=list(fields))
        audit.record(
            user=user,
            channel=channel,
            action=entry.action,
            target_type=entry.target_type,
            target_id=entry.target_id,
            target_label=str(instance),
            before=before_now,
            after=_snapshot(resource, instance),
            reverts=entry,
        )

    return handler


def _snapshot(resource: catalog.Resource, instance) -> dict:
    instance = type(instance)._default_manager.get(pk=instance.pk)
    return audit.json_safe(resource.view.serializer_class(instance).data)
