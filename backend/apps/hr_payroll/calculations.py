"""
Gross-to-net payroll calculation (REQ-HR-003). Pure functions, no model/DB
dependency, so the arithmetic can be tested in isolation from PayrollRun's
orchestration -- see rates.py's module docstring for the disclaimer on the
constants this applies.
"""

from decimal import ROUND_HALF_UP, Decimal

from . import rates

CENTS = Decimal("0.01")


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(CENTS, rounding=ROUND_HALF_UP)


def _apply_brackets(amount: Decimal, brackets: list[tuple[Decimal | None, Decimal]]) -> Decimal:
    """Standard marginal-rate bracket calculation -- each bracket's rate
    applies only to the slice of `amount` within that bracket, not the whole
    amount (that's the difference between marginal and flat-rate tax)."""
    tax = Decimal("0")
    lower = Decimal("0")
    for upper, rate in brackets:
        if upper is None or amount <= upper:
            tax += (amount - lower) * rate
            break
        tax += (upper - lower) * rate
        lower = upper
    return tax


def calculate_payslip(gross_salary: Decimal) -> dict:
    """
    Returns every component of a single employee's monthly payslip for a
    given gross salary. See rates.py for what's simplified/unverified here.
    """
    gross_salary = Decimal(str(gross_salary))

    sgk_employee_premium = _round(gross_salary * rates.SGK_EMPLOYEE_RATE)
    unemployment_employee_premium = _round(gross_salary * rates.UNEMPLOYMENT_EMPLOYEE_RATE)
    taxable_income = gross_salary - sgk_employee_premium - unemployment_employee_premium
    income_tax = _round(_apply_brackets(taxable_income, rates.INCOME_TAX_BRACKETS_MONTHLY))
    stamp_duty = _round(gross_salary * rates.STAMP_DUTY_RATE)

    net_salary = gross_salary - sgk_employee_premium - unemployment_employee_premium - income_tax - stamp_duty

    employer_sgk_cost = _round(gross_salary * rates.SGK_EMPLOYER_RATE)
    employer_unemployment_cost = _round(gross_salary * rates.UNEMPLOYMENT_EMPLOYER_RATE)
    total_employer_cost = gross_salary + employer_sgk_cost + employer_unemployment_cost

    return {
        "gross_salary": gross_salary,
        "sgk_employee_premium": sgk_employee_premium,
        "unemployment_employee_premium": unemployment_employee_premium,
        "income_tax": income_tax,
        "stamp_duty": stamp_duty,
        "net_salary": net_salary,
        "employer_sgk_cost": employer_sgk_cost,
        "employer_unemployment_cost": employer_unemployment_cost,
        "total_employer_cost": total_employer_cost,
    }
