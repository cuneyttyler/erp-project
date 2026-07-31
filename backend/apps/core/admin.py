from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Account, AuditLogEntry, JournalEntry, JournalLine, Role, User


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
