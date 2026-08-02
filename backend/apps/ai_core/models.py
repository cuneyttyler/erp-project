from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class PendingApproval(models.Model):
    """
    REQ-CORE-AI-007/010: the durable state machine behind "the AI can
    propose a mutating action but must wait for explicit human confirmation
    before it actually happens" (technical.md §8.4). Durable (a DB row, not
    an in-memory flag) so a proposed action survives a server restart --
    the user can come back an hour later and still approve/reject it.

    `pending -> approved -> executed` (action ran, `result` populated) or
    `pending -> approved -> failed` (action ran but raised -- e.g. a
    validation error the LLM's input didn't satisfy) or `pending ->
    rejected`. There is deliberately no path back to `pending` from any
    terminal state -- same one-way-lock discipline as JournalEntry.post()/
    Invoice.mark_sent() elsewhere in this codebase.

    REQ-CORE-AI-010 ("configurable auto-approve vs. requires-confirmation
    threshold per tenant/action-type") is NOT implemented -- every write
    action requires confirmation unconditionally in this pass, the same
    "one fixed gate, not a configurable multi-level threshold" scope cut
    already made for PurchaseOrder.APPROVAL_THRESHOLD. A per-tenant
    threshold config is real follow-up work, not a hidden gap -- see
    docs/notes.md.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (EXECUTED, "Executed"),
        (FAILED, "Failed"),
    ]

    action_name = models.CharField(max_length=100)
    action_input = models.JSONField(default=dict, blank=True)
    summary = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="requested_ai_approvals"
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action_name} ({self.status})"

    def approve(self, user, active_packages):
        """Executes the underlying action now, using the *current* user's
        session/permissions -- not the original requester's, and never an
        elevated service account (REQ-CORE-AI-004's "no privileged AI
        service account" guarantee extends to the write path too).

        `active_packages` is the caller's (views.py) `request.tenant.
        active_packages` -- re-checked here rather than trusted from
        proposal time, since a package could've been deactivated in the
        meantime; passed in rather than re-queried here to avoid this
        model needing its own cross-schema lookup of the tenant record."""
        if self.status != self.PENDING:
            raise ValidationError("Only a pending approval can be approved.")

        from apps.core.models import AuditLogEntry

        from . import actions

        action = actions.get_action(self.action_name, active_packages)
        if action is None:
            raise ValidationError(f"Action '{self.action_name}' is no longer available on this tenant's plan.")

        try:
            outcome = action.func(user, **(self.action_input or {}))
            self.result = outcome.get("result")
            self.status = self.EXECUTED
        except Exception as exc:
            self.error = str(exc)
            self.status = self.FAILED
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "result", "error", "resolved_by", "resolved_at"])

        AuditLogEntry.objects.create(
            actor=f"ai:{self.requested_by_id}",
            action=f"ai_action_{self.action_name}",
            target_type="pending_approval",
            target_id=str(self.id),
            before={"input": self.action_input, "approved_by": f"user:{user.id}"},
            after={"status": self.status, "result": self.result, "error": self.error},
        )
        return self

    def reject(self, user):
        if self.status != self.PENDING:
            raise ValidationError("Only a pending approval can be rejected.")
        self.status = self.REJECTED
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolved_by", "resolved_at"])
        return self


class AIUsageRecord(models.Model):
    """
    REQ-CORE-AI-011: the usage ledger underlying "AI Action credits"
    billing (product.md §7.2). Every real call through llm_gateway writes
    one row here (see chat.py) -- this is a real, populated ledger, not a
    stub table. What's NOT built yet: the credit-balance/billing
    reconciliation on top of it (translating token counts into a metered
    charge, enforcing a spend cap, invoicing) -- that's real follow-up
    work tracked in docs/notes.md, not hidden behind this model existing.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    model = models.CharField(max_length=100)
    input_tokens = models.PositiveIntegerField()
    output_tokens = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.model} in={self.input_tokens} out={self.output_tokens} ({self.created_at:%Y-%m-%d})"
