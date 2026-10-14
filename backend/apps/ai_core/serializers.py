from rest_framework import serializers

from apps.access.permissions import allowed

from .models import Conversation, ConversationMessage, PendingApproval


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=4000)
    locale = serializers.ChoiceField(choices=["tr", "en"], default="en")
    # Omitted to start a new conversation.
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    # The company selected in the header, which scopes finance data.
    entity = serializers.IntegerField(required=False, allow_null=True)


class PendingApprovalSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True)
    resolved_by_username = serializers.CharField(source="resolved_by.username", read_only=True, default=None)
    can_approve = serializers.SerializerMethodField()

    class Meta:
        model = PendingApproval
        fields = [
            "id",
            "action_name",
            "resource",
            "operation",
            "target_id",
            "action_input",
            "preview",
            "summary",
            "status",
            "can_approve",
            "requested_by_username",
            "resolved_by_username",
            "result",
            "error",
            "created_at",
            "resolved_at",
        ]
        read_only_fields = fields

    def get_can_approve(self, approval) -> bool:
        request = self.context.get("request")
        if request is None or approval.status != PendingApproval.PENDING:
            return False
        return allowed(request.user, getattr(request, "tenant", None), approval.action_name)


def hydrate_blocks(blocks: list, request) -> list:
    """Stored blocks reference a proposal by id; what's sent to the browser
    carries the proposal as it stands *now* -- so a conversation reopened
    tomorrow shows which proposals were approved, not a stale "pending"."""
    ids = [block["approval_id"] for block in blocks if block.get("type") == "proposal"]
    if not ids:
        return blocks
    approvals = {a.id: a for a in PendingApproval.objects.filter(id__in=ids).select_related("requested_by", "resolved_by")}
    hydrated = []
    for block in blocks:
        if block.get("type") != "proposal":
            hydrated.append(block)
        elif block["approval_id"] in approvals:
            data = PendingApprovalSerializer(approvals[block["approval_id"]], context={"request": request}).data
            hydrated.append({"type": "proposal", "approval": data})
    return hydrated


class ConversationMessageSerializer(serializers.ModelSerializer):
    blocks = serializers.SerializerMethodField()

    class Meta:
        model = ConversationMessage
        fields = ["id", "role", "text", "blocks", "citations", "created_at"]

    def get_blocks(self, message) -> list:
        return hydrate_blocks(message.blocks or [], self.context.get("request"))


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "title", "created_at", "updated_at"]


class ConversationDetailSerializer(ConversationSerializer):
    messages = ConversationMessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = [*ConversationSerializer.Meta.fields, "messages"]
