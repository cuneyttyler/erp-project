"""HR & Payroll tests (REQ-HR-001/002/003)."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import User
from apps.hr_payroll.calculations import calculate_payslip
from apps.hr_payroll.models import Employee, LeaveRequest, PayrollRun


class CalculatePayslipTests(TenantTestCase):
    """Pure-function arithmetic checks -- no DB dependency, but grouped
    under TenantTestCase for consistency with the rest of the suite."""

    def test_net_salary_is_gross_minus_all_deductions(self):
        figures = calculate_payslip(Decimal("30000.00"))
        expected_net = (
            figures["gross_salary"]
            - figures["sgk_employee_premium"]
            - figures["unemployment_employee_premium"]
            - figures["income_tax"]
            - figures["stamp_duty"]
        )
        self.assertEqual(figures["net_salary"], expected_net)

    def test_employer_cost_exceeds_gross_by_employer_side_premiums(self):
        figures = calculate_payslip(Decimal("30000.00"))
        expected_total = figures["gross_salary"] + figures["employer_sgk_cost"] + figures["employer_unemployment_cost"]
        self.assertEqual(figures["total_employer_cost"], expected_total)

    def test_income_tax_uses_marginal_brackets_not_flat_rate(self):
        # Taxable income straddling the first two brackets (9000 / 19000) --
        # a flat-rate calculation at the top marginal rate would overshoot.
        figures = calculate_payslip(Decimal("20000.00"))
        # taxable = 20000 - sgk(14%) - unemployment(1%) = 20000 - 2800 - 200 = 17000
        # bracket: 9000 * 0.15 + (17000-9000) * 0.20 = 1350 + 1600 = 2950.00
        self.assertEqual(figures["income_tax"], Decimal("2950.00"))


class LeaveRequestLifecycleTests(TenantTestCase):
    def setUp(self):
        self.employee = Employee.objects.create(
            first_name="Ayşe", last_name="Yılmaz", hire_date="2024-01-15", monthly_gross_salary=Decimal("30000.00")
        )

    def test_approve_pending_request(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee, start_date="2026-08-01", end_date="2026-08-05"
        )
        leave.approve()
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.APPROVED)

    def test_cannot_approve_twice(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee, start_date="2026-08-01", end_date="2026-08-05"
        )
        leave.approve()
        with self.assertRaises(ValidationError):
            leave.approve()

    def test_reject_pending_request(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee, start_date="2026-08-01", end_date="2026-08-05"
        )
        leave.reject()
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.REJECTED)

    def test_days_is_inclusive(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee, start_date="2026-08-01", end_date="2026-08-05"
        )
        leave.refresh_from_db()
        self.assertEqual(leave.days, 5)


class PayrollRunTests(TenantTestCase):
    def setUp(self):
        self.active_employee = Employee.objects.create(
            first_name="Ayşe", last_name="Yılmaz", hire_date="2024-01-15", monthly_gross_salary=Decimal("30000.00")
        )
        self.inactive_employee = Employee.objects.create(
            first_name="Mehmet",
            last_name="Demir",
            hire_date="2020-01-01",
            monthly_gross_salary=Decimal("40000.00"),
            is_active=False,
        )
        self.run = PayrollRun.objects.create(period_year=2026, period_month=8)

    def test_calculate_creates_payslips_for_active_employees_only(self):
        self.run.calculate()
        self.assertEqual(self.run.payslips.count(), 1)
        self.assertEqual(self.run.payslips.first().employee, self.active_employee)

    def test_calculate_is_idempotent(self):
        self.run.calculate()
        self.run.calculate()
        self.assertEqual(self.run.payslips.count(), 1)

    def test_calculate_fills_in_newly_added_employee_without_duplicating(self):
        self.run.calculate()
        new_employee = Employee.objects.create(
            first_name="Elif", last_name="Kaya", hire_date="2026-07-01", monthly_gross_salary=Decimal("25000.00")
        )
        self.run.calculate()
        self.assertEqual(self.run.payslips.count(), 2)
        self.assertTrue(self.run.payslips.filter(employee=new_employee).exists())

    def test_cannot_calculate_a_finalized_run(self):
        self.run.calculate()
        self.run.finalize()
        with self.assertRaises(ValidationError):
            self.run.calculate()

    def test_cannot_finalize_with_no_payslips(self):
        with self.assertRaises(ValidationError):
            self.run.finalize()

    def test_cannot_finalize_twice(self):
        self.run.calculate()
        self.run.finalize()
        with self.assertRaises(ValidationError):
            self.run.finalize()


class PayrollRunAPITests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="hr-admin", password="x")
        self.employee = Employee.objects.create(
            first_name="Ayşe", last_name="Yılmaz", hire_date="2024-01-15", monthly_gross_salary=Decimal("30000.00")
        )
        self.tenant.active_packages = ["hr_payroll"]
        self.tenant.save()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_calculate_response_reflects_fresh_payslips_not_stale_prefetch_cache(self):
        # Regression test for the same prefetch-staleness bug class fixed in
        # purchasing/sales_crm: fetch the run via the viewset's own
        # prefetch_related("payslips__employee") queryset BEFORE calculate()
        # inserts any payslips, mirroring what self.get_object() does inside
        # the action, then confirm the API response isn't served from that
        # now-stale cached empty list.
        run = PayrollRun.objects.create(period_year=2026, period_month=8)
        from apps.hr_payroll.models import PayrollRun as PayrollRunModel

        PayrollRunModel.objects.prefetch_related("payslips__employee").get(id=run.id)

        response = self.client.post(
            f"/api/v1/hr-payroll/payroll-runs/{run.id}/calculate/", HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.data["payslips"]), 1)
        self.assertEqual(response.data["payslips"][0]["employee"], self.employee.id)

    def test_finalize_then_cannot_recalculate(self):
        run = PayrollRun.objects.create(period_year=2026, period_month=9)
        self.client.post(f"/api/v1/hr-payroll/payroll-runs/{run.id}/calculate/", HTTP_HOST="tenant.test.com")
        finalize_response = self.client.post(
            f"/api/v1/hr-payroll/payroll-runs/{run.id}/finalize/", HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(finalize_response.status_code, 200, finalize_response.content)
        recalculate_response = self.client.post(
            f"/api/v1/hr-payroll/payroll-runs/{run.id}/calculate/", HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(recalculate_response.status_code, 400)

    def test_tenant_without_hr_payroll_package_is_forbidden(self):
        self.tenant.active_packages = []
        self.tenant.save()
        response = self.client.get("/api/v1/hr-payroll/employees/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 403)
