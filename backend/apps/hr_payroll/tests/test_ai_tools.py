from decimal import Decimal

from django_tenants.test.cases import TenantTestCase

from apps.core.models import User
from apps.hr_payroll.ai_tools import (
    _approve_leave_request_preview,
    active_employee_count,
    approve_leave_request,
    latest_payroll_cost,
)
from apps.hr_payroll.models import Employee, LeaveRequest, PayrollRun


class LatestPayrollCostMetricTests(TenantTestCase):
    def setUp(self):
        Employee.objects.create(
            first_name="Ayşe", last_name="Yılmaz", hire_date="2024-01-15", monthly_gross_salary=Decimal("30000.00")
        )

    def test_no_runs_returns_a_message_not_an_error(self):
        outcome = latest_payroll_cost()
        self.assertIn("message", outcome["result"])

    def test_returns_most_recent_period_with_correct_totals(self):
        older = PayrollRun.objects.create(period_year=2026, period_month=6)
        older.calculate()
        newer = PayrollRun.objects.create(period_year=2026, period_month=7)
        newer.calculate()

        outcome = latest_payroll_cost()
        self.assertEqual(outcome["result"]["period"], "2026-07")
        self.assertEqual(outcome["result"]["employee_count"], 1)
        # gross 30000, employer sgk 15.5% = 4650, employer unemployment 2% = 600
        self.assertEqual(outcome["result"]["total_employer_cost"], "35250.00")


class ActiveEmployeeCountMetricTests(TenantTestCase):
    def test_counts_only_active_employees(self):
        Employee.objects.create(
            first_name="Ayşe", last_name="Yılmaz", hire_date="2024-01-15",
            monthly_gross_salary=Decimal("30000.00"), is_active=True,
        )
        Employee.objects.create(
            first_name="Mehmet", last_name="Demir", hire_date="2020-01-01",
            monthly_gross_salary=Decimal("40000.00"), is_active=False,
        )
        outcome = active_employee_count()
        self.assertEqual(outcome["result"]["active_employee_count"], 1)


class ApproveLeaveRequestActionTests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="asker", password="x")
        self.employee = Employee.objects.create(
            first_name="Ayşe", last_name="Yılmaz", hire_date="2024-01-15", monthly_gross_salary=Decimal("30000.00")
        )
        self.leave = LeaveRequest.objects.create(
            employee=self.employee, leave_type=LeaveRequest.ANNUAL, start_date="2026-08-10", end_date="2026-08-14"
        )

    def test_approves_a_pending_leave_request(self):
        outcome = approve_leave_request(self.user, leave_request_id=self.leave.id)
        self.leave.refresh_from_db()
        self.assertEqual(self.leave.status, LeaveRequest.APPROVED)
        self.assertEqual(outcome["result"]["status"], LeaveRequest.APPROVED)

    def test_approving_an_already_approved_request_raises(self):
        self.leave.approve()
        with self.assertRaises(ValueError):
            approve_leave_request(self.user, leave_request_id=self.leave.id)

    def test_approving_a_nonexistent_request_raises(self):
        with self.assertRaises(ValueError):
            approve_leave_request(self.user, leave_request_id=999999)


class ApproveLeaveRequestPreviewTests(TenantTestCase):
    def setUp(self):
        self.employee = Employee.objects.create(
            first_name="Ayşe", last_name="Yılmaz", hire_date="2024-01-15", monthly_gross_salary=Decimal("30000.00")
        )
        self.leave = LeaveRequest.objects.create(
            employee=self.employee, leave_type=LeaveRequest.ANNUAL, start_date="2026-08-10", end_date="2026-08-14"
        )

    def test_preview_mentions_employee_and_dates(self):
        preview = _approve_leave_request_preview(leave_request_id=self.leave.id)
        self.assertIn("Ayşe Yılmaz", preview)
        self.assertIn("2026-08-10", preview)

    def test_preview_for_unknown_request_does_not_raise(self):
        preview = _approve_leave_request_preview(leave_request_id=999999)
        self.assertIn("999999", preview)
