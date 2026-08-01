from decimal import Decimal

from django_tenants.test.cases import TenantTestCase

from apps.hr_payroll.ai_tools import active_employee_count, latest_payroll_cost
from apps.hr_payroll.models import Employee, PayrollRun


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
