"""HR & Payroll's read-only AI metrics (technical.md §8.2/§8.4). Registered
from HrPayrollConfig.ready() -- see apps/hr_payroll/apps.py."""

from decimal import Decimal

from apps.ai_core.semantic import register_metric

from .models import Employee, PayrollRun


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
