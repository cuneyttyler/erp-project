from rest_framework import serializers

from .models import PendingApproval


class ChatHistoryTurnSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField()


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=4000)
    locale = serializers.ChoiceField(choices=["tr", "en"], default="en")
    history = ChatHistoryTurnSerializer(many=True, required=False, default=list)


class CitationSerializer(serializers.Serializer):
    label = serializers.CharField()
    route = serializers.CharField()


class PendingActionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    description = serializers.CharField()


class ChatResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()
    citations = CitationSerializer(many=True)
    configured = serializers.BooleanField()
    pending_action = PendingActionSerializer(allow_null=True)


class PendingApprovalSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True)

    class Meta:
        model = PendingApproval
        fields = [
            "id",
            "action_name",
            "action_input",
            "summary",
            "status",
            "requested_by_username",
            "result",
            "error",
            "created_at",
            "resolved_at",
        ]
        read_only_fields = fields
