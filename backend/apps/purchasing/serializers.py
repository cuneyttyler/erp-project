from decimal import Decimal

from rest_framework import serializers

from .models import PurchaseOrder, PurchaseOrderLine


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    quantity_remaining = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseOrderLine
        fields = [
            "id",
            "item",
            "item_sku",
            "item_name",
            "quantity_ordered",
            "quantity_received",
            "quantity_remaining",
            "unit_price",
            "amount",
        ]
        read_only_fields = ["quantity_received"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    """REQ-PUR-001/002. `total`/`requires_approval` are model properties
    (models.py) -- routed through explicit fields for the same reason as
    every other computed financial figure in this codebase (see
    TrialBalanceRowSerializer's docstring): never a bare float."""

    lines = PurchaseOrderLineSerializer(many=True)
    party_name = serializers.CharField(source="party.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    requires_approval = serializers.BooleanField(read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "party",
            "party_name",
            "warehouse",
            "warehouse_code",
            "order_date",
            "expected_date",
            "status",
            "memo",
            "lines",
            "total",
            "requires_approval",
            "approved_at",
            "approved_by",
            "created_at",
        ]
        read_only_fields = ["status", "approved_at", "approved_by", "created_at"]

    def validate_lines(self, lines):
        if not lines:
            raise serializers.ValidationError("A purchase order needs at least one line.")
        return lines

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        order = PurchaseOrder.objects.create(**validated_data)
        for line_data in lines_data:
            line_data.pop("quantity_received", None)
            PurchaseOrderLine.objects.create(purchase_order=order, **line_data)
        return order


class ReceiveLineSerializer(serializers.Serializer):
    line_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))


class ReceiveSerializer(serializers.Serializer):
    lines = ReceiveLineSerializer(many=True)

    def validate_lines(self, lines):
        if not lines:
            raise serializers.ValidationError("Provide at least one line to receive.")
        return lines
