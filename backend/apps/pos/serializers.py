from rest_framework import serializers

from .models import POSPayment, POSReturn, POSReturnLine, POSSale, POSSaleLine, POSShift, Store, Till


class StoreSerializer(serializers.ModelSerializer):
    entity_code = serializers.CharField(source="entity.code", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = Store
        fields = ["id", "entity", "entity_code", "warehouse", "warehouse_code", "code", "name", "is_active"]


class TillSerializer(serializers.ModelSerializer):
    store_code = serializers.CharField(source="store.code", read_only=True)

    class Meta:
        model = Till
        fields = ["id", "store", "store_code", "code", "name", "is_active"]


class POSShiftSerializer(serializers.ModelSerializer):
    till_label = serializers.CharField(source="till.__str__", read_only=True)
    opened_by_username = serializers.CharField(source="opened_by.username", read_only=True)

    class Meta:
        model = POSShift
        fields = [
            "id",
            "till",
            "till_label",
            "opened_by",
            "opened_by_username",
            "opening_cash",
            "closing_cash_counted",
            "status",
            "opened_at",
            "closed_at",
        ]
        read_only_fields = ["opened_by", "closing_cash_counted", "status", "opened_at", "closed_at"]


class CloseShiftSerializer(serializers.Serializer):
    closing_cash_counted = serializers.DecimalField(max_digits=14, decimal_places=2)


class POSSaleLineSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)
    line_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = POSSaleLine
        fields = [
            "id",
            "item",
            "item_sku",
            "item_name",
            "quantity",
            "unit_price",
            "discount_amount",
            "quantity_returned",
            "line_total",
        ]


class POSPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = POSPayment
        fields = ["id", "method", "amount"]


class POSSaleSerializer(serializers.ModelSerializer):
    lines = POSSaleLineSerializer(many=True, read_only=True)
    payments = POSPaymentSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = POSSale
        fields = [
            "id",
            "shift",
            "status",
            "client_reference",
            "created_by_username",
            "journal_entry",
            "lines",
            "payments",
            "subtotal",
            "created_at",
        ]
        read_only_fields = fields


class CheckoutLineInputSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2)
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=2)
    discount_amount = serializers.DecimalField(max_digits=14, decimal_places=2, default=0)


class CheckoutPaymentInputSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=POSPayment.METHOD_CHOICES)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class CheckoutSerializer(serializers.Serializer):
    """The request body for `POSShiftViewSet.checkout` -- deliberately a
    plain input serializer (not POSSaleSerializer) since a checkout request
    describes lines/payments to *create*, not a POSSale's own read shape."""

    lines = CheckoutLineInputSerializer(many=True)
    payments = CheckoutPaymentInputSerializer(many=True)
    client_reference = serializers.CharField(required=False, allow_blank=True, default="")


class POSReturnLineSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="sale_line.item.sku", read_only=True)

    class Meta:
        model = POSReturnLine
        fields = ["id", "sale_line", "item_sku", "quantity", "refund_amount"]


class POSReturnSerializer(serializers.ModelSerializer):
    lines = POSReturnLineSerializer(many=True, read_only=True)

    class Meta:
        model = POSReturn
        fields = ["id", "sale", "refund_method", "reason", "journal_entry", "lines", "created_at"]
        read_only_fields = fields


class ReturnLineInputSerializer(serializers.Serializer):
    sale_line_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2)


class ReturnSaleSerializer(serializers.Serializer):
    lines = ReturnLineInputSerializer(many=True)
    refund_method = serializers.ChoiceField(choices=POSPayment.METHOD_CHOICES)
    reason = serializers.CharField(required=False, allow_blank=True, default="")
