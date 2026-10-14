from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    """
    One thread with the assistant, kept so a user can come back to it.

    Two representations are stored, for two different readers:

    - `messages` (ConversationMessage rows) is what the *person* saw: each
      turn's text plus the structured blocks rendered with it (tables,
      charts, proposals).
    - `llm_messages` is what the *model* needs to continue: the exact
      Messages-API transcript, including the tool calls and tool results in
      between. Without those, a follow-up like "send the second one" would
      have nothing to resolve "the second one" against.

    Private to its owner -- a conversation can quote any record its owner
    was allowed to read, so it isn't shared with anyone, admins included.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_conversations")
    title = models.CharField(max_length=120)
    llm_messages = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title


class ConversationMessage(models.Model):
    USER = "user"
    ASSISTANT = "assistant"
    ROLE_CHOICES = [(USER, "User"), (ASSISTANT, "Assistant")]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    text = models.TextField(blank=True)
    # What was rendered alongside the text -- see apps/ai_core/tools.py for
    # the block shapes (table, chart, record, proposal).
    blocks = models.JSONField(default=list, blank=True)
    citations = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.role}: {self.text[:40]}"


class PendingApproval(models.Model):
    """
    REQ-CORE-AI-007/010: the durable state machine behind "the assistant can
    propose a change but a person must confirm it before it happens"
    (technical.md §8.4). Durable (a DB row, not an in-memory flag) so a
    proposal survives a server restart -- the user can come back an hour
    later and still approve or reject it.

    A proposal is one action from the catalog (apps.access): `resource` +
    `operation`, the record it targets, and the request body. It was checked
    when it was proposed (permission, the record exists, the body validates
    -- apps.access.dispatch.check), and `preview` holds what the person is
    shown: the record's name and, for an update, exactly which fields change
    from what to what.

    `pending -> executed` (the action ran; `result` is what it returned) or
    `pending -> failed` (it ran and was refused, e.g. by a business rule
    only the handler knows -- nothing was changed) or `pending -> rejected`.
    There is deliberately no path back to `pending` from a terminal state --
    same one-way discipline as JournalEntry.post()/Invoice.mark_sent().

    REQ-CORE-AI-010 ("configurable auto-approve vs. requires-confirmation
    threshold per tenant/action-type") is NOT implemented -- every write the
    assistant proposes requires confirmation, unconditionally. A per-tenant
    threshold is real follow-up work, not a hidden gap -- see docs/notes.md.
    """

    PENDING = "pending"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (REJECTED, "Rejected"),
        (EXECUTED, "Executed"),
        (FAILED, "Failed"),
    ]

    # The catalog code, `<resource>.<operation>` -- kept alongside the two
    # parts so it reads on its own in the admin site and in exports.
    action_name = models.CharField(max_length=100)
    # Blank only on proposals recorded before proposals were catalog
    # actions; those can no longer be approved.
    resource = models.CharField(max_length=100, blank=True, default="")
    operation = models.CharField(max_length=100, blank=True, default="")
    target_id = models.CharField(max_length=64, blank=True)
    action_input = models.JSONField(default=dict, blank=True)
    preview = models.JSONField(default=dict, blank=True)
    summary = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    conversation = models.ForeignKey(Conversation, null=True, blank=True, on_delete=models.SET_NULL, related_name="proposals")
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

    def approve(self, user, tenant):
        """Performs the action now, as `user` -- the person approving, who
        may not be the person who asked. It goes through the resource's own
        API view (apps.access.dispatch), so it is validated again, checked
        against *this* user's permissions, and logged in the audit trail
        with channel "ai" and this user as the one responsible. There is no
        AI service account: the assistant never holds a permission the
        approver doesn't (REQ-CORE-AI-004)."""
        if self.status != self.PENDING:
            raise ValidationError("Only a pending proposal can be approved.")

        from apps.access import audit, catalog, dispatch
        from apps.access.permissions import allowed

        if not allowed(user, tenant, self.action_name):
            # Refused before anything runs, and left pending: someone who
            # does hold the permission can still approve it.
            raise ValidationError("You don't have permission to perform this action.")

        outcome = dispatch.perform(
            user,
            tenant,
            self.resource,
            self.operation,
            pk=self.target_id or None,
            data=self.action_input or {},
            channel=audit.AI,
            # The assistant proposes only the fields that change.
            handler="partial_update" if self.operation == catalog.UPDATE else None,
        )
        if outcome.ok:
            self.status, self.result = self.EXECUTED, outcome.data
        else:
            self.status, self.error = self.FAILED, outcome.error
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "result", "error", "resolved_by", "resolved_at"])
        self._tell_the_conversation(
            f"was approved by {user.username} and carried out. Result: {outcome.data}"
            if outcome.ok
            else f"was approved by {user.username} but FAILED and changed nothing. Error: {outcome.error}"
        )
        return self

    def reject(self, user):
        if self.status != self.PENDING:
            raise ValidationError("Only a pending proposal can be rejected.")
        self.status = self.REJECTED
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolved_by", "resolved_at"])
        self._tell_the_conversation(f"was rejected by {user.username}. Nothing was changed.")
        return self

    def _tell_the_conversation(self, what_happened: str):
        """Leaves a note in the conversation's model-side transcript, so the
        assistant's next reply knows how its proposal turned out instead of
        still describing it as waiting."""
        if self.conversation_id is None:
            return
        conversation = self.conversation
        note = f"[System note, not typed by the user] Proposal #{self.id} ({self.action_name}) {what_happened}"
        conversation.llm_messages = [*conversation.llm_messages, {"role": "user", "content": note[:4000]}]
        conversation.save(update_fields=["llm_messages", "updated_at"])


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
