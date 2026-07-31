from decimal import Decimal

from rest_framework import serializers

from apps.core.models import Item

from .models import StockMove, Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "code", "name", "is_active"]


class StockMoveSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = StockMove
        fields = [
            "id",
            "item",
            "item_sku",
            "item_name",
            "warehouse",
            "warehouse_code",
            "move_type",
            "quantity",
            "reference",
            "created_at",
        ]
        read_only_fields = ["move_type", "created_at"]


class TransferSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=Item.objects.all())
    from_warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    to_warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    reference = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, data):
        if data["from_warehouse"] == data["to_warehouse"]:
            raise serializers.ValidationError("Source and destination warehouse must differ.")
        return data


class StockLevelRowSerializer(serializers.Serializer):
    """
    Explicit serializer for the stock-on-hand aggregation, same discipline as
    TrialBalanceRowSerializer/AgingRowSerializer: quantity_on_hand must
    serialize as a precise decimal string, never a bare float.
    """

    item_sku = serializers.CharField()
    item_name = serializers.CharField()
    warehouse_code = serializers.CharField()
    warehouse_name = serializers.CharField()
    quantity_on_hand = serializers.DecimalField(max_digits=14, decimal_places=2)
