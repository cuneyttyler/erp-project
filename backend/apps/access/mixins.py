from django.db import transaction
from rest_framework.permissions import SAFE_METHODS

from . import audit, catalog
from .permissions import HasActionPermission


class ResourceViewMixin:
    """
    What every catalog resource's view shares. Put in front of the view by
    the `@resource` decorator (catalog.py) -- never listed as a base by hand.

    For each request it works out which catalog operation is being performed
    and then:

    1. checks the user holds that action (after the view's own permission
       classes have run);
    2. runs a write inside one database transaction together with its audit
       entry, so a change and its log row either both happen or neither
       does; and
    3. records the audit entry, with the record as serialized before and
       after -- which is all revert.py needs to undo it later.

    Because this sits on the view rather than on any one caller, it applies
    identically to a click in a screen and to the assistant acting through
    dispatch.py.
    """

    resource: catalog.Resource

    def resource_operation(self):
        """The catalog operation this request performs, or None."""
        handler = getattr(self, "action", None) or self.request.method.lower()
        return self.resource.handler_ops.get(handler)

    def get_permissions(self):
        return [*super().get_permissions(), HasActionPermission()]

    def dispatch(self, request, *args, **kwargs):
        if request.method in SAFE_METHODS:
            return super().dispatch(request, *args, **kwargs)
        with transaction.atomic():
            response = super().dispatch(request, *args, **kwargs)
            if response.status_code >= 400:
                # A handler that returns an error after partly writing
                # (rather than raising) must not leave that half behind.
                transaction.set_rollback(True)
            return response

    # -- audit ------------------------------------------------------------
    def _is_audited_write(self) -> bool:
        operation = self.resource_operation()
        return operation is not None and self.resource.operations[operation].kind == catalog.WRITE

    def _snapshot(self, instance):
        serializer_class = getattr(self, "serializer_class", None) or self.get_serializer_class()
        return audit.json_safe(serializer_class(instance, context=self.get_serializer_context()).data)

    def _model(self):
        queryset = getattr(self, "queryset", None)
        return (queryset if queryset is not None else self.get_queryset()).model

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # Capture the record as it stands before a write to it. Runs after
        # authentication and permission checks (that's what super().initial
        # does), so nothing is read for a request that's about to be refused.
        self._audit_before = None
        self._audit_label = ""
        if self._is_audited_write() and self.resource.is_viewset and self.kwargs.get(getattr(self, "lookup_url_kwarg", None) or getattr(self, "lookup_field", "pk")):
            instance = self.get_object()
            self._audit_before = self._snapshot(instance)
            self._audit_label = str(instance)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        # `_audit_before` is only set once initial() got past the permission
        # checks -- a refused request never reaches here with it.
        if response.status_code < 400 and hasattr(self, "_audit_before") and self._is_audited_write():
            self._record_audit(request, response)
        return response

    def _record_audit(self, request, response):
        operation = self.resource_operation()
        before, label = self._audit_before, self._audit_label
        after = None
        target_id = ""

        if before is not None:
            target_id = before.get("id", "") if isinstance(before, dict) else ""
            target_id = target_id or self.kwargs.get("pk", "")
            if operation != catalog.DELETE:
                # Re-read rather than trust the response body: a transition
                # may answer with something other than the record itself
                # (PurchaseOrder.receive returns the order plus a bill).
                instance = self._model()._default_manager.filter(pk=target_id).first()
                if instance is not None:
                    after = self._snapshot(instance)
                    label = str(instance)
        else:
            # A create, or a collection-level action: the response is the
            # only description there is of what was made.
            after = audit.json_safe(response.data)
            if isinstance(after, dict) and after.get("id") is not None:
                target_id = after["id"]
                if self.resource.is_viewset:
                    instance = self._model()._default_manager.filter(pk=target_id).first()
                    label = str(instance) if instance is not None else ""

        reverts_id = getattr(request, audit.REVERTS_ATTR, None)
        audit.record(
            user=request.user,
            channel=audit.channel_of(request),
            action=self.resource.code(operation),
            target_type=self.resource.key,
            target_id=target_id,
            target_label=label,
            before=before,
            after=after,
            reverts=audit.AuditLogEntry.objects.filter(pk=reverts_id).first() if reverts_id else None,
        )
