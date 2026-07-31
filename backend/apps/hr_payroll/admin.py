from django.contrib import admin

from .models import Employee, LeaveRequest, PayrollRun, Payslip


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "position", "department", "monthly_gross_salary", "is_active")
    list_filter = ("department", "is_active")
    search_fields = ("first_name", "last_name", "national_id")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "status")
    list_filter = ("status", "leave_type")


class PayslipInline(admin.TabularInline):
    model = Payslip
    extra = 0
    readonly_fields = [f.name for f in Payslip._meta.fields if f.name != "id"]
    can_delete = False


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ("period_year", "period_month", "status", "created_at")
    list_filter = ("status",)
    inlines = [PayslipInline]
