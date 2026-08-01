from rest_framework import serializers


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


class ChatResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()
    citations = CitationSerializer(many=True)
    configured = serializers.BooleanField()
