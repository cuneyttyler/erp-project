from decimal import Decimal

from rest_framework import serializers

from .models import Employee, LeaveRequest, PayrollRun, Payslip


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            "id",
            "first_name",
            "last_name",
            "national_id",
            "position",
            "department",
            "hire_date",
            "monthly_gross_salary",
            "is_active",
        ]


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.__str__", read_only=True)
    days = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee",
            "employee_name",
            "leave_type",
            "start_date",
            "end_date",
            "days",
            "status",
            "reason",
            "created_at",
        ]
        read_only_fields = ["status", "created_at"]


class PayslipSerializer(serializers.ModelSerializer):
    """All money fields here are real model DecimalField columns, not
    computed properties -- ModelSerializer already generates
    coerce_to_string=True DecimalFields for those automatically, so (unlike
    TrialBalanceRowSerializer/PurchaseOrderSerializer.total/etc.) no explicit
    override is needed to avoid the float-coercion bug."""

    employee_name = serializers.CharField(source="employee.__str__", read_only=True)

    class Meta:
        model = Payslip
        fields = [
            "id",
            "employee",
            "employee_name",
            "gross_salary",
            "sgk_employee_premium",
            "unemployment_employee_premium",
            "income_tax",
            "stamp_duty",
            "net_salary",
            "employer_sgk_cost",
            "employer_unemployment_cost",
            "total_employer_cost",
        ]


class PayrollRunSerializer(serializers.ModelSerializer):
    payslips = PayslipSerializer(many=True, read_only=True)

    class Meta:
        model = PayrollRun
        fields = ["id", "period_year", "period_month", "status", "payslips", "created_at"]
        read_only_fields = ["status", "created_at"]
