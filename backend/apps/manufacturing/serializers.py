from decimal import Decimal

from rest_framework import serializers

from .models import BOM, BOMLine, WorkOrder


class BOMLineSerializer(serializers.ModelSerializer):
    component_sku = serializers.CharField(source="component_item.sku", read_only=True)
    component_name = serializers.CharField(source="component_item.name", read_only=True)

    class Meta:
        model = BOMLine
        fields = ["id", "component_item", "component_sku", "component_name", "quantity_per"]


class BOMSerializer(serializers.ModelSerializer):
    lines = BOMLineSerializer(many=True)
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)

    class Meta:
        model = BOM
        fields = ["id", "item", "item_sku", "item_name", "name", "is_active", "lines", "created_at"]
        read_only_fields = ["created_at"]

    def validate_lines(self, lines):
        if not lines:
            raise serializers.ValidationError("A BOM needs at least one component line.")
        return lines

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        bom = BOM.objects.create(**validated_data)
        for line_data in lines_data:
            BOMLine.objects.create(bom=bom, **line_data)
        return bom


class WorkOrderSerializer(serializers.ModelSerializer):
    """`quantity_remaining` is a model property -- routed through an explicit
    DecimalField for the same reason as every other computed figure in this
    codebase (see TrialBalanceRowSerializer's docstring): never a bare float."""

    bom_item_sku = serializers.CharField(source="bom.item.sku", read_only=True)
    bom_item_name = serializers.CharField(source="bom.item.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    quantity_remaining = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = WorkOrder
        fields = [
            "id",
            "bom",
            "bom_item_sku",
            "bom_item_name",
            "warehouse",
            "warehouse_code",
            "quantity_planned",
            "quantity_completed",
            "quantity_remaining",
            "status",
            "scheduled_date",
            "memo",
            "created_at",
        ]
        read_only_fields = ["quantity_completed", "status", "created_at"]


class CompleteWorkOrderSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
