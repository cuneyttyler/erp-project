from decimal import Decimal

from rest_framework import serializers

from .models import Lead, SalesOrder, SalesOrderLine


class LeadSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source="party.name", read_only=True)

    class Meta:
        model = Lead
        fields = ["id", "name", "party", "party_name", "status", "source", "notes", "created_at"]
        read_only_fields = ["status", "created_at"]


class SalesOrderLineSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    quantity_remaining = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = SalesOrderLine
        fields = [
            "id",
            "item",
            "item_sku",
            "item_name",
            "quantity_ordered",
            "quantity_fulfilled",
            "quantity_remaining",
            "unit_price",
            "amount",
        ]
        read_only_fields = ["quantity_fulfilled"]


class SalesOrderSerializer(serializers.ModelSerializer):
    """REQ-CRM-002/003. `total` routed through an explicit DecimalField for
    the same reason as every other computed financial figure in this
    codebase (see TrialBalanceRowSerializer's docstring): never a bare float."""

    lines = SalesOrderLineSerializer(many=True)
    party_name = serializers.CharField(source="party.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = SalesOrder
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
            "created_at",
        ]
        read_only_fields = ["status", "created_at"]

    def validate_lines(self, lines):
        if not lines:
            raise serializers.ValidationError("A sales order needs at least one line.")
        return lines

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        order = SalesOrder.objects.create(**validated_data)
        for line_data in lines_data:
            line_data.pop("quantity_fulfilled", None)
            SalesOrderLine.objects.create(sales_order=order, **line_data)
        return order


class FulfillLineSerializer(serializers.Serializer):
    line_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))


class FulfillSerializer(serializers.Serializer):
    lines = FulfillLineSerializer(many=True)

    def validate_lines(self, lines):
        if not lines:
            raise serializers.ValidationError("Provide at least one line to fulfill.")
        return lines
