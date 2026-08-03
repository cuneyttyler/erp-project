from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasActivePackage

from . import services
from .models import MarketplaceAccount, MarketplaceListing, MarketplaceOrder
from .serializers import (
    MarketplaceAccountSerializer,
    MarketplaceListingSerializer,
    MarketplaceOrderSerializer,
    SyncResultSerializer,
)


class MarketplaceAccountViewSet(viewsets.ModelViewSet):
    """REQ-ECOM-001/003."""

    permission_classes = [IsAuthenticated, HasActivePackage("ecommerce")]
    queryset = MarketplaceAccount.objects.select_related("entity", "warehouse").all()
    serializer_class = MarketplaceAccountSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["platform", "is_active", "entity"]

    @action(detail=True, methods=["post"], url_path="sync-orders")
    def sync_orders(self, request, pk=None):
        account = self.get_object()
        try:
            result = services.sync_orders(account)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            # A marketplace HTTP call failing (auth error, timeout, rate
            # limit) is an external-integration failure, not a 500 in our
            # own code -- degrade to a 502 with the reason rather than an
            # opaque server error (REQ-CORE-AI-009's "degrade gracefully"
            # discipline, applied to this integration too).
            return Response({"detail": f"Marketplace sync failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(SyncResultSerializer(result).data)

    @action(detail=True, methods=["post"], url_path="push-stock")
    def push_stock(self, request, pk=None):
        account = self.get_object()
        try:
            result = services.push_stock_levels(account)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": f"Marketplace stock push failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(SyncResultSerializer(result).data)


class MarketplaceListingViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasActivePackage("ecommerce")]
    queryset = MarketplaceListing.objects.select_related("account", "item").all()
    serializer_class = MarketplaceListingSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["account", "is_active"]


class MarketplaceOrderViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only -- a MarketplaceOrder is only ever created by
    `services.sync_orders`, never directly through the API."""

    permission_classes = [IsAuthenticated, HasActivePackage("ecommerce")]
    queryset = MarketplaceOrder.objects.select_related("account", "sales_order").all()
    serializer_class = MarketplaceOrderSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["account", "status"]
