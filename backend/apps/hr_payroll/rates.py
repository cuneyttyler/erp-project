"""
Turkish payroll rate constants (REQ-HR-003).

*** THESE ARE ILLUSTRATIVE PLACEHOLDER VALUES. ***

SGK premium rates, unemployment insurance rates, income tax brackets, the
minimum wage, and the stamp duty rate are all set by the Turkish government
and change at least annually (frequently mid-year too, and the minimum wage
specifically is revised every January). None of the figures below have been
verified against current Resmi Gazete publications. DO NOT run a real
payroll with these values without a qualified Turkish payroll specialist or
mali müşavir confirming every constant here first.

This mirrors technical.md §7.2's `thresholds.py` pattern for GİB compliance
thresholds: every legally-set number lives in one place, versioned and
clearly labeled, never silently hardcoded inline in calculation logic --
that discipline is what makes it possible to update these safely later
(a data change, not a logic change) once real figures are confirmed.
"""

from decimal import Decimal

RATES_EFFECTIVE_YEAR = 2026  # bump this alongside every constant below when rates are updated

SGK_EMPLOYEE_RATE = Decimal("0.14")  # employee-side SGK premium (14% has been stable for years)
SGK_EMPLOYER_RATE = Decimal("0.155")  # employer-side, assumes the standard 5-point incentive applies
UNEMPLOYMENT_EMPLOYEE_RATE = Decimal("0.01")
UNEMPLOYMENT_EMPLOYER_RATE = Decimal("0.02")
STAMP_DUTY_RATE = Decimal("0.00759")

MINIMUM_WAGE_MONTHLY_GROSS = Decimal("26005.50")  # PLACEHOLDER -- verify current asgari ücret

# Monthly income tax brackets -- SIMPLIFIED, not true cumulative-annual
# calculation. Real Turkish income tax (gelir vergisi) is cumulative within
# the calendar year: an employee's tax bracket depends on their year-to-date
# taxable earnings, not just the current month in isolation. This engine
# applies the bracket table fresh each month, which understates tax due
# later in the year once cumulative earnings cross a bracket threshold.
# Also NOT implemented: the minimum-wage income-tax/stamp-duty exemption
# (asgari ücret istisnası) that reduces liability for lower earners. Both are
# real correctness gaps for a production payroll run, flagged here rather
# than silently approximated as if they were handled.
#
# Each tuple is (upper bound of bracket in monthly TRY, marginal rate).
# `None` upper bound = no ceiling (top bracket).
INCOME_TAX_BRACKETS_MONTHLY = [
    (Decimal("9000"), Decimal("0.15")),
    (Decimal("19000"), Decimal("0.20")),
    (Decimal("45000"), Decimal("0.27")),
    (Decimal("150000"), Decimal("0.35")),
    (None, Decimal("0.40")),
]
