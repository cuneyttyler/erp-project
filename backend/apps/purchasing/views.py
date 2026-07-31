from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasActivePackage
from apps.core.serializers import BillSerializer

from .models import PurchaseOrder
from .serializers import PurchaseOrderSerializer, ReceiveSerializer


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """REQ-PUR-001 to 007 (except AI drafting/vendor-price-comparison,
    deferred -- see requirements.md §5.1)."""

    permission_classes = [IsAuthenticated, HasActivePackage("purchasing")]
    queryset = (
        PurchaseOrder.objects.select_related("party", "warehouse")
        .prefetch_related("lines__item")
        .all()
    )
    serializer_class = PurchaseOrderSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "party"]

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        order = self.get_object()
        try:
            order.approve(request.user)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def send_document(self, request, pk=None):
        order = self.get_object()
        try:
            order.mark_sent()
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        order = self.get_object()
        serializer = ReceiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            bill = order.receive(serializer.validated_data["lines"])
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # `order` was fetched via this viewset's prefetch_related("lines__item")
        # queryset, so its cached `.lines.all()` still holds the pre-receive
        # snapshot even though receive() just updated those rows through
        # separately-fetched objects (models.py's `fresh_lines` comment) --
        # re-fetching here is what keeps *this response* (not just the
        # internal status check) showing real quantity_received/remaining
        # values instead of stale ones.
        order = self.get_queryset().get(pk=order.pk)
        return Response(
            {
                "purchase_order": self.get_serializer(order).data,
                "generated_bill": BillSerializer(bill).data,
            }
        )
