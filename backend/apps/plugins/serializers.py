from rest_framework import serializers

from .registry import SIZES, get_widget


class PluginToggleSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField()


class WidgetLayoutEntrySerializer(serializers.Serializer):
    key = serializers.CharField(max_length=100)
    is_enabled = serializers.BooleanField()
    size = serializers.ChoiceField(choices=SIZES)

    def validate_key(self, value):
        if get_widget(value) is None:
            raise serializers.ValidationError(f"Unknown widget '{value}'.")
        return value


class WidgetLayoutSerializer(serializers.Serializer):
    # List order is the panel order.
    widgets = WidgetLayoutEntrySerializer(many=True)

    def validate_widgets(self, value):
        keys = [entry["key"] for entry in value]
        if len(keys) != len(set(keys)):
            raise serializers.ValidationError("A widget can only appear once in the layout.")
        return value
