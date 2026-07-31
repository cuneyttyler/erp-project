from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction

from .calculations import calculate_payslip


class Employee(models.Model):
    """REQ-HR-001. `national_id` is the employee's TCKN -- checksum
    validation (REQ-DATA-003) belongs to the migration/onboarding import
    path, not enforced on free-form entry here, same as Party.tax_id."""

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    national_id = models.CharField(max_length=11, blank=True)
    position = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    hire_date = models.DateField()
    monthly_gross_salary = models.DecimalField(max_digits=14, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class LeaveRequest(models.Model):
    """
    REQ-HR-002. `days` is a plain calendar-day count, not adjusted for
    weekends/public holidays or Turkish statutory leave-entitlement rules
    (which scale with tenure -- 14/20/26 days depending on years of
    service). That entitlement calculation is a real feature deferred here,
    same discipline as every other explicitly-noted scope cut in this
    codebase -- this models the *request/approval workflow*, not entitlement
    accounting.
    """

    ANNUAL = "annual"
    SICK = "sick"
    LEAVE_TYPE_CHOICES = [(ANNUAL, "Annual"), (SICK, "Sick")]

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATUS_CHOICES = [(PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected")]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=10, choices=LEAVE_TYPE_CHOICES, default=ANNUAL)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return f"{self.employee} {self.leave_type} {self.start_date}–{self.end_date}"

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    def approve(self):
        if self.status != self.PENDING:
            raise ValidationError("Only a pending leave request can be approved.")
        self.status = self.APPROVED
        self.save(update_fields=["status"])

    def reject(self):
        if self.status != self.PENDING:
            raise ValidationError("Only a pending leave request can be rejected.")
        self.status = self.REJECTED
        self.save(update_fields=["status"])


class PayrollRun(models.Model):
    """
    REQ-HR-003. draft -> finalized. `calculate()` generates one Payslip per
    active Employee for this period (idempotent -- re-running it only fills
    in employees who don't have a payslip in this run yet, never duplicates
    or overwrites one that exists). `finalize()` is the one-way lock, same
    shape as JournalEntry.post()/Invoice.mark_sent() elsewhere in this
    codebase: a draft run can be recalculated freely, a finalized one can't.

    REQ-HR-004 (monthly SGK e-Bildirge submission) is explicitly NOT
    implemented here -- see docs/notes.md: it's blocked on the same GİB
    compliance-partner decision (technical.md §7.1) as e-Fatura, since
    e-Bildirge submission requires the same kind of GİB-facing integration.
    This model produces the payroll figures that submission would eventually
    transmit; it doesn't transmit them.
    """

    DRAFT = "draft"
    FINALIZED = "finalized"
    STATUS_CHOICES = [(DRAFT, "Draft"), (FINALIZED, "Finalized")]

    period_year = models.PositiveIntegerField()
    period_month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_year", "-period_month"]
        unique_together = ["period_year", "period_month"]

    def __str__(self) -> str:
        return f"Payroll {self.period_year}-{self.period_month:02d}"

    @transaction.atomic
    def calculate(self):
        if self.status != self.DRAFT:
            raise ValidationError("Only a draft payroll run can be (re)calculated.")
        existing_employee_ids = set(self.payslips.values_list("employee_id", flat=True))
        created = []
        for employee in Employee.objects.filter(is_active=True).exclude(id__in=existing_employee_ids):
            figures = calculate_payslip(employee.monthly_gross_salary)
            created.append(Payslip.objects.create(payroll_run=self, employee=employee, **figures))
        return created

    def finalize(self):
        if self.status != self.DRAFT:
            raise ValidationError("Only a draft payroll run can be finalized.")
        if not self.payslips.exists():
            raise ValidationError("Cannot finalize a payroll run with no payslips -- run calculate() first.")
        self.status = self.FINALIZED
        self.save(update_fields=["status"])


class Payslip(models.Model):
    """One employee's computed pay for one PayrollRun -- see
    calculations.calculate_payslip() for what each field means and
    rates.py for the rates it was computed from."""

    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="payslips")

    gross_salary = models.DecimalField(max_digits=14, decimal_places=2)
    sgk_employee_premium = models.DecimalField(max_digits=14, decimal_places=2)
    unemployment_employee_premium = models.DecimalField(max_digits=14, decimal_places=2)
    income_tax = models.DecimalField(max_digits=14, decimal_places=2)
    stamp_duty = models.DecimalField(max_digits=14, decimal_places=2)
    net_salary = models.DecimalField(max_digits=14, decimal_places=2)
    employer_sgk_cost = models.DecimalField(max_digits=14, decimal_places=2)
    employer_unemployment_cost = models.DecimalField(max_digits=14, decimal_places=2)
    total_employer_cost = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        unique_together = ["payroll_run", "employee"]
        ordering = ["employee__last_name"]

    def __str__(self) -> str:
        return f"{self.employee} — {self.payroll_run}"
