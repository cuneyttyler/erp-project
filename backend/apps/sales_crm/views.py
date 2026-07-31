from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasActivePackage
from apps.core.serializers import InvoiceSerializer

from .models import Lead, SalesOrder
from .serializers import FulfillSerializer, LeadSerializer, SalesOrderSerializer


class LeadViewSet(viewsets.ModelViewSet):
    """REQ-CRM-001."""

    permission_classes = [IsAuthenticated, HasActivePackage("sales_crm")]
    queryset = Lead.objects.select_related("party").all()
    serializer_class = LeadSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status"]

    @action(detail=True, methods=["post"])
    def qualify(self, request, pk=None):
        lead = self.get_object()
        try:
            lead.qualify()
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(lead).data)

    @action(detail=True, methods=["post"])
    def mark_won(self, request, pk=None):
        lead = self.get_object()
        party_id = request.data.get("party")
        if not party_id:
            return Response({"detail": "party is required."}, status=status.HTTP_400_BAD_REQUEST)
        from apps.core.models import Party

        try:
            party = Party.objects.get(id=party_id)
            lead.mark_won(party)
        except (ValidationError, Party.DoesNotExist) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(lead).data)

    @action(detail=True, methods=["post"])
    def mark_lost(self, request, pk=None):
        lead = self.get_object()
        try:
            lead.mark_lost()
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(lead).data)


class SalesOrderViewSet(viewsets.ModelViewSet):
    """REQ-CRM-002/003."""

    permission_classes = [IsAuthenticated, HasActivePackage("sales_crm")]
    queryset = (
        SalesOrder.objects.select_related("party", "warehouse").prefetch_related("lines__item").all()
    )
    serializer_class = SalesOrderSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "party"]

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        order = self.get_object()
        try:
            order.confirm()
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def fulfill(self, request, pk=None):
        order = self.get_object()
        serializer = FulfillSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invoice = order.fulfill(serializer.validated_data["lines"])
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # Re-fetch: `order` came from this viewset's prefetch_related("lines__item")
        # queryset, whose cached `.lines.all()` snapshot predates fulfill()'s own
        # line updates (same prefetch-staleness class of bug fixed in
        # purchasing/views.py's receive() -- see that file's comment).
        order = self.get_queryset().get(pk=order.pk)
        return Response(
            {
                "sales_order": self.get_serializer(order).data,
                "generated_invoice": InvoiceSerializer(invoice).data,
            }
        )
