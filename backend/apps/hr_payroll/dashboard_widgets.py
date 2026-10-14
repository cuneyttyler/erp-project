"""HR & Payroll's home-panel widgets. Registered from HrPayrollConfig.ready()."""

from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from apps.plugins import registry as r

from .models import Employee, LeaveRequest, PayrollRun

ZERO = Decimal("0")


@r.register_widget("headcount", plugin="hr_payroll", kind=r.STAT, order=190)
def headcount(ctx: r.WidgetContext) -> dict:
    today = timezone.localdate()
    active = Employee.objects.filter(is_active=True)
    on_leave = (
        LeaveRequest.objects.filter(status=LeaveRequest.APPROVED, start_date__lte=today, end_date__gte=today)
        .values("employee")
        .distinct()
        .count()
    )
    return r.stat(
        active.count(),
        "number",
        secondary=[
            r.secondary("monthly_gross_payroll", active.aggregate(total=Sum("monthly_gross_salary"))["total"] or ZERO, "money"),
            r.secondary("on_leave_today", on_leave),
        ],
        route="/employees",
    )


@r.register_widget("pending_leave_requests", plugin="hr_payroll", kind=r.TABLE, order=700)
def pending_leave_requests(ctx: r.WidgetContext) -> dict:
    pending = LeaveRequest.objects.filter(status=LeaveRequest.PENDING).select_related("employee").order_by("start_date")
    rows = [
        {
            "employee": f"{lr.employee.first_name} {lr.employee.last_name}",
            "leave_type": lr.leave_type,
            "start_date": str(lr.start_date),
            "end_date": str(lr.end_date),
            "days": lr.days,
        }
        for lr in pending[:8]
    ]
    return r.table(
        [("employee", "text"), ("leave_type", "status"), ("start_date", "date"), ("end_date", "date"), ("days", "number")],
        rows,
        route="/leave-requests",
        total_count=pending.count(),
    )


@r.register_widget("payroll_cost_trend", plugin="hr_payroll", kind=r.CHART, order=710, default_enabled=False)
def payroll_cost_trend(ctx: r.WidgetContext) -> dict:
    """Total employer cost of the last six finalized payroll runs."""
    runs = (
        PayrollRun.objects.filter(status=PayrollRun.FINALIZED)
        .annotate(cost=Sum("payslips__total_employer_cost"))
        .order_by("-period_year", "-period_month")[:6]
    )
    points = [(f"{run.period_year:04d}-{run.period_month:02d}", run.cost or ZERO) for run in reversed(list(runs))]
    return r.chart("line", [r.series("employer_cost", points)], label_kind="month", route="/payroll-runs")


@r.register_widget("headcount_by_department", plugin="hr_payroll", kind=r.CHART, order=720, default_enabled=False)
def headcount_by_department(ctx: r.WidgetContext) -> dict:
    counts = Employee.objects.filter(is_active=True).values_list("department").annotate(n=Count("id")).order_by("-n")[:8]
    # A blank department is sent as an empty label; the frontend prints its
    # own "unassigned" wording for it.
    return r.chart("hbar", [r.series("employees", [(department, n) for department, n in counts])], fmt="number", route="/employees")


@r.register_attention("hr_payroll")
def _hr_attention(ctx: r.WidgetContext) -> list:
    return [
        r.attention_item("pending_leave_requests", LeaveRequest.objects.filter(status=LeaveRequest.PENDING).count(), r.WARNING, "/leave-requests"),
        r.attention_item("draft_payroll_runs", PayrollRun.objects.filter(status=PayrollRun.DRAFT).count(), r.INFO, "/payroll-runs"),
    ]
