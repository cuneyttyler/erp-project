from rest_framework import serializers

from .models import MarketplaceAccount, MarketplaceListing, MarketplaceOrder


class MarketplaceAccountSerializer(serializers.ModelSerializer):
    entity_code = serializers.CharField(source="entity.code", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = MarketplaceAccount
        fields = [
            "id",
            "platform",
            "name",
            "entity",
            "entity_code",
            "warehouse",
            "warehouse_code",
            "shop_domain",
            "api_key",
            "api_secret",
            "is_active",
            "last_synced_at",
            "created_at",
        ]
        read_only_fields = ["last_synced_at", "created_at"]
        # Credentials are write-only -- a client can set/rotate them but the
        # API never echoes them back, in a list or a retrieve (models.py's
        # docstring on why this is the current mitigation, not real
        # at-rest encryption).
        extra_kwargs = {
            "api_key": {"write_only": True},
            "api_secret": {"write_only": True},
        }


class MarketplaceListingSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)

    class Meta:
        model = MarketplaceListing
        fields = [
            "id",
            "account",
            "item",
            "item_sku",
            "item_name",
            "external_sku",
            "external_variant_id",
            "external_location_id",
            "is_active",
        ]


class MarketplaceOrderSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = MarketplaceOrder
        fields = [
            "id",
            "account",
            "account_name",
            "external_order_id",
            "status",
            "sales_order",
            "error",
            "synced_at",
            "created_at",
        ]
        read_only_fields = fields


class SyncResultSerializer(serializers.Serializer):
    created = serializers.IntegerField(required=False)
    skipped = serializers.IntegerField(required=False)
    failed = serializers.IntegerField()
    pushed = serializers.IntegerField(required=False)
