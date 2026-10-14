"""HR & Payroll's home-panel widgets. Registered from HrPayrollConfig.ready()."""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from apps.plugins import registry as r
from apps.plugins.periods import month_key, month_starts

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


# Page charts (see apps/core/dashboard_widgets.py).
@r.register_widget("salary_by_department", plugin="hr_payroll", kind=r.CHART, order=1500, default_enabled=False)
def salary_by_department(ctx: r.WidgetContext) -> dict:
    """Monthly gross salaries of active employees, per department."""
    rows = (
        Employee.objects.filter(is_active=True)
        .values("department")
        .annotate(total=Sum("monthly_gross_salary"))
        .order_by("-total")[:8]
    )
    return r.chart("hbar", [r.series("gross_salary", [(row["department"], row["total"]) for row in rows])], route="/employees")


@r.register_widget("leave_days_trend", plugin="hr_payroll", kind=r.CHART, order=1510, default_enabled=False)
def leave_days_trend(ctx: r.WidgetContext) -> dict:
    """Approved leave days per month (by start date), annual and sick, last
    six months."""
    starts = month_starts(6)
    days = defaultdict(int)
    for leave in LeaveRequest.objects.filter(status=LeaveRequest.APPROVED, start_date__gte=starts[0]):
        days[(month_key(leave.start_date), leave.leave_type)] += leave.days
    return r.chart(
        "bar",
        [
            r.series("annual_leave", [(month_key(s), days[(month_key(s), LeaveRequest.ANNUAL)]) for s in starts]),
            r.series("sick_leave", [(month_key(s), days[(month_key(s), LeaveRequest.SICK)]) for s in starts]),
        ],
        fmt="number",
        label_kind="month",
        route="/leave-requests",
    )


@r.register_widget("payroll_breakdown", plugin="hr_payroll", kind=r.CHART, order=1520, default_enabled=False)
def payroll_breakdown(ctx: r.WidgetContext) -> dict:
    """Where the latest finalized payroll's money goes: what employees take
    home, the deductions from their gross, and the employer's own premiums."""
    run = PayrollRun.objects.filter(status=PayrollRun.FINALIZED).order_by("-period_year", "-period_month").first()
    fields = [
        ("net_salary", "net_salary"),
        ("income_tax", "income_tax"),
        ("sgk_employee", "sgk_employee_premium"),
        ("employer_sgk", "employer_sgk_cost"),
        ("unemployment", "unemployment_employee_premium"),
        ("employer_unemployment", "employer_unemployment_cost"),
        ("stamp_duty", "stamp_duty"),
    ]
    sums = run.payslips.aggregate(**{key: Sum(field) for key, field in fields}) if run else {}
    return r.chart("hbar", [r.series("amount", [(key, sums.get(key) or ZERO) for key, _ in fields])], label_kind="key", route="/payroll-runs")
