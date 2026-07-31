from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Account,
    AuditLogEntry,
    Bill,
    BillLine,
    Invoice,
    InvoiceLine,
    JournalEntry,
    JournalLine,
    Party,
    Payment,
    Role,
    User,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("ERP settings", {"fields": ("mfa_enabled", "preferred_locale")}),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target_type", "target_id")
    list_filter = ("action", "target_type")
    search_fields = ("actor", "target_id")

    def has_change_permission(self, request, obj=None):
        # Append-only per REQ-CORE-AUDIT-002 -- not even an admin can edit these.
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account_type", "parent", "is_active")
    list_filter = ("account_type", "is_active")
    search_fields = ("code", "name")


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 2


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "memo", "status", "created_by", "posted_at")
    list_filter = ("status",)
    inlines = [JournalLineInline]
    readonly_fields = ("posted_at",)

    def has_change_permission(self, request, obj=None):
        # Posted entries are immutable (REQ-CORE-GL-008) -- drafts stay editable.
        if obj is not None and obj.status == JournalEntry.POSTED:
            return False
        return super().has_change_permission(request, obj)


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ("name", "party_type", "tax_id", "email", "is_active")
    list_filter = ("party_type", "is_active")
    search_fields = ("name", "tax_id", "email")


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "party", "issue_date", "due_date", "status")
    list_filter = ("status",)
    inlines = [InvoiceLineInline]


class BillLineInline(admin.TabularInline):
    model = BillLine
    extra = 1


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ("id", "party", "issue_date", "due_date", "status")
    list_filter = ("status",)
    inlines = [BillLineInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "amount", "invoice", "bill", "method")
    list_filter = ("method",)
