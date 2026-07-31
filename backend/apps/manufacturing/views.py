from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasActivePackage

from .models import BOM, WorkOrder
from .serializers import BOMSerializer, CompleteWorkOrderSerializer, WorkOrderSerializer


class BOMViewSet(viewsets.ModelViewSet):
    """REQ-MFG-001."""

    permission_classes = [IsAuthenticated, HasActivePackage("manufacturing")]
    queryset = BOM.objects.select_related("item").prefetch_related("lines__component_item").all()
    serializer_class = BOMSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_active", "item"]


class WorkOrderViewSet(viewsets.ModelViewSet):
    """REQ-MFG-002."""

    permission_classes = [IsAuthenticated, HasActivePackage("manufacturing")]
    queryset = WorkOrder.objects.select_related("bom__item", "warehouse").all()
    serializer_class = WorkOrderSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "bom"]

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        order = self.get_object()
        try:
            order.release()
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        order = self.get_object()
        serializer = CompleteWorkOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order.complete(serializer.validated_data["quantity"])
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(order).data)
