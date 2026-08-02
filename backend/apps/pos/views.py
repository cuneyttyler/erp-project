from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasActivePackage

from . import services
from .models import POSReturn, POSSale, POSShift, Store, Till
from .serializers import (
    CheckoutSerializer,
    CloseShiftSerializer,
    POSReturnSerializer,
    POSSaleSerializer,
    POSShiftSerializer,
    ReturnSaleSerializer,
    StoreSerializer,
    TillSerializer,
)


class StoreViewSet(viewsets.ModelViewSet):
    """REQ-POS-002."""

    permission_classes = [IsAuthenticated, HasActivePackage("pos")]
    queryset = Store.objects.select_related("entity", "warehouse").all()
    serializer_class = StoreSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_active", "entity"]


class TillViewSet(viewsets.ModelViewSet):
    """REQ-POS-002."""

    permission_classes = [IsAuthenticated, HasActivePackage("pos")]
    queryset = Till.objects.select_related("store").all()
    serializer_class = TillSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_active", "store"]


class POSShiftViewSet(viewsets.ModelViewSet):
    """REQ-POS-001/004. Checkout, close, and the Z-report all hang off the
    shift they belong to -- there's no route to take a POS sale outside a
    shift's lifetime (see `POSShift.__doc__`)."""

    permission_classes = [IsAuthenticated, HasActivePackage("pos")]
    queryset = POSShift.objects.select_related("till__store", "opened_by").all()
    serializer_class = POSShiftSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "till"]

    def perform_create(self, serializer):
        serializer.save(opened_by=self.request.user)

    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        shift = self.get_object()
        body = CheckoutSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            sale = services.checkout(
                shift,
                lines=body.validated_data["lines"],
                payments=body.validated_data["payments"],
                user=request.user,
                client_reference=body.validated_data.get("client_reference", ""),
            )
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(POSSaleSerializer(sale).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        shift = self.get_object()
        body = CloseShiftSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            shift.close(body.validated_data["closing_cash_counted"])
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(shift).data)

    @action(detail=True, methods=["get"], url_path="z-report")
    def z_report(self, request, pk=None):
        shift = self.get_object()
        return Response(shift.z_report())


class POSSaleViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only -- a sale is only ever created via
    `POSShiftViewSet.checkout` and only ever amended via
    `POSSaleViewSet.return_sale`, never a generic update/delete."""

    permission_classes = [IsAuthenticated, HasActivePackage("pos")]
    queryset = POSSale.objects.select_related("shift__till__store", "created_by").prefetch_related(
        "lines__item", "payments"
    )
    serializer_class = POSSaleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "shift"]

    @action(detail=True, methods=["post"], url_path="return")
    def return_sale(self, request, pk=None):
        sale = self.get_object()
        body = ReturnSaleSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            pos_return = services.return_sale(
                sale,
                lines=body.validated_data["lines"],
                user=request.user,
                refund_method=body.validated_data["refund_method"],
                reason=body.validated_data.get("reason", ""),
            )
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(POSReturnSerializer(pos_return).data, status=status.HTTP_201_CREATED)


class POSReturnViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, HasActivePackage("pos")]
    queryset = POSReturn.objects.select_related("sale", "created_by").prefetch_related("lines__sale_line__item")
    serializer_class = POSReturnSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["sale"]
