"""HR & Payroll's read-only AI metrics and write actions (technical.md
§8.2/§8.4). Registered from HrPayrollConfig.ready() -- see
apps/hr_payroll/apps.py."""

from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.ai_core.actions import register_action
from apps.ai_core.semantic import register_metric

from .models import Employee, LeaveRequest, PayrollRun


@register_metric(
    name="latest_payroll_cost",
    description="The most recent payroll run's total employer cost (gross salaries plus employer-side SGK/unemployment premiums) and net payout to employees.",
    input_schema={"type": "object", "properties": {}},
    package="hr_payroll",
)
def latest_payroll_cost(**_kwargs) -> dict:
    run = PayrollRun.objects.prefetch_related("payslips").order_by("-period_year", "-period_month").first()
    if run is None:
        return {"result": {"message": "No payroll runs exist yet."}, "citations": []}
    total_employer_cost = sum((p.total_employer_cost for p in run.payslips.all()), Decimal("0"))
    total_net = sum((p.net_salary for p in run.payslips.all()), Decimal("0"))
    return {
        "result": {
            "period": f"{run.period_year}-{run.period_month:02d}",
            "status": run.status,
            "employee_count": run.payslips.count(),
            "total_employer_cost": str(total_employer_cost),
            "total_net_payout": str(total_net),
        },
        "citations": [{"label": "Bordro Dönemleri / Payroll Runs", "route": "/payroll-runs"}],
    }


@register_metric(
    name="active_employee_count",
    description="Count of currently active employees.",
    input_schema={"type": "object", "properties": {}},
    package="hr_payroll",
)
def active_employee_count(**_kwargs) -> dict:
    count = Employee.objects.filter(is_active=True).count()
    return {
        "result": {"active_employee_count": count},
        "citations": [{"label": "Çalışanlar / Employees", "route": "/employees"}],
    }


def _approve_leave_request_preview(leave_request_id=None, **_kwargs) -> str:
    try:
        leave = LeaveRequest.objects.select_related("employee").get(id=leave_request_id)
    except LeaveRequest.DoesNotExist:
        return f"İzin talebi #{leave_request_id} bulunamadı."
    return (
        f"{leave.employee}'nin {leave.start_date} - {leave.end_date} tarihli izin talebi "
        f"({leave.get_leave_type_display()}) onaylanacak."
    )


@register_action(
    name="approve_leave_request",
    description="Approve a pending leave request. Reuses the same LeaveRequest.approve() model method the Leave Requests screen's own approve button calls.",
    input_schema={
        "type": "object",
        "properties": {"leave_request_id": {"type": "integer"}},
        "required": ["leave_request_id"],
    },
    package="hr_payroll",
    preview=_approve_leave_request_preview,
)
def approve_leave_request(user, leave_request_id=None) -> dict:
    try:
        leave = LeaveRequest.objects.select_related("employee").get(id=leave_request_id)
    except LeaveRequest.DoesNotExist as exc:
        raise ValueError(f"Leave request #{leave_request_id} does not exist.") from exc
    try:
        leave.approve()
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    return {
        "result": {"id": leave.id, "status": leave.status},
        "summary": f"Approved {leave.employee}'s leave request ({leave.start_date} to {leave.end_date}).",
    }
