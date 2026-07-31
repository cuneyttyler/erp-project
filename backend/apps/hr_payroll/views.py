from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasActivePackage

from .models import Employee, LeaveRequest, PayrollRun
from .serializers import EmployeeSerializer, LeaveRequestSerializer, PayrollRunSerializer


class EmployeeViewSet(viewsets.ModelViewSet):
    """REQ-HR-001. Note: no field-level restriction on salary visibility yet
    (e.g. hiding monthly_gross_salary from non-payroll roles) -- the same
    known gap as every other package today (REQ-CORE-USR-003 field-level
    permissions aren't built out per-module yet); flagged here explicitly
    since payroll data is more sensitive than most, not because this
    package is uniquely behind the others."""

    permission_classes = [IsAuthenticated, HasActivePackage("hr_payroll")]
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_active", "department"]


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """REQ-HR-002."""

    permission_classes = [IsAuthenticated, HasActivePackage("hr_payroll")]
    queryset = LeaveRequest.objects.select_related("employee").all()
    serializer_class = LeaveRequestSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "employee", "leave_type"]

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        leave = self.get_object()
        try:
            leave.approve()
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(leave).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        leave = self.get_object()
        try:
            leave.reject()
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(leave).data)


class PayrollRunViewSet(viewsets.ModelViewSet):
    """REQ-HR-003. See models.py's PayrollRun docstring re: REQ-HR-004
    (SGK e-Bildirge submission) being explicitly out of scope here."""

    permission_classes = [IsAuthenticated, HasActivePackage("hr_payroll")]
    queryset = PayrollRun.objects.prefetch_related("payslips__employee").all()
    serializer_class = PayrollRunSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "period_year", "period_month"]

    @action(detail=True, methods=["post"])
    def calculate(self, request, pk=None):
        run = self.get_object()
        try:
            run.calculate()
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # Re-fetch: `run` came from this viewset's prefetch_related("payslips__employee")
        # queryset, whose cached snapshot predates calculate()'s own inserts --
        # same prefetch-staleness class of bug fixed in purchasing/sales_crm
        # (see those apps' receive()/fulfill() view comments).
        run = self.get_queryset().get(pk=run.pk)
        return Response(self.get_serializer(run).data)

    @action(detail=True, methods=["post"])
    def finalize(self, request, pk=None):
        run = self.get_object()
        try:
            run.finalize()
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(run).data)
