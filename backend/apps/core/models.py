from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Tenant-scoped user account (technical.md §5 `User`). Lives inside each
    tenant's own schema — `apps.core` is a TENANT_APP, not a SHARED_APP.

    The external-accountant cross-tenant case (REQ-CORE-USR-006) is deliberately
    NOT modeled as a `tenant` FK here — a user row lives in one tenant's schema by
    definition. Cross-tenant accountant access is handled by a separate
    `TenantAccess` record living in the shared/public schema (apps.tenants),
    linking an accountant's identity to the tenants they're permitted into,
    without duplicating their user row per tenant. That model lands alongside
    the accountant-facing UI in a later phase — flagged here so the shape isn't
    forgotten once real accounts are being modeled.
    """

    mfa_enabled = models.BooleanField(default=False)
    preferred_locale = models.CharField(max_length=10, default="tr")

    def __str__(self) -> str:
        return self.get_full_name() or self.username


class Role(models.Model):
    """
    RBAC role (REQ-CORE-USR-002/003). `granted_actions` is a per-module action
    map, e.g. {"purchasing": ["view", "create", "approve"], "hr_payroll": ["view"]}.
    Field-level restrictions (REQ-CORE-USR-003) are enforced at the serializer
    layer per package app, not modeled generically here.
    """

    name = models.CharField(max_length=100, unique=True)
    granted_actions = models.JSONField(default=dict, blank=True)
    users = models.ManyToManyField(User, related_name="roles", blank=True)

    def __str__(self) -> str:
        return self.name


class AuditLogEntry(models.Model):
    """
    Append-only audit trail (REQ-CORE-AUDIT-001/002). No update/delete path is
    exposed anywhere in the application layer; production deployments additionally
    enforce this at the database permission level (technical.md §8.6) via an
    INSERT-only Postgres role — that DB-level grant is an infra/migration concern
    tracked separately, not something this model can express on its own.

    AI-originated entries reuse this same table (technical.md §8.6 `AIActionLog`
    is a specialized sibling of this model, not a replacement for it) — `actor`
    is "user:<id>" for a human action or "ai:<user_id>" for an AI action taken on
    that user's behalf, per REQ-CORE-AUDIT-003.
    """

    actor = models.CharField(max_length=255)
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=64)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "audit log entries"

    def __str__(self) -> str:
        return f"{self.actor} {self.action} {self.target_type}:{self.target_id}"


class Account(models.Model):
    """
    Chart of Accounts entry (technical.md §5, REQ-CORE-GL-001). Ships with a
    Turkish Tekdüzen Hesap Planı-based seed (see `apps/core/fixtures/`
    and `management/commands/seed_chart_of_accounts.py`), but the model itself
    is generic/international so a non-Turkish COA template can be seeded the
    same way in a later localization pack.
    """

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"
    ACCOUNT_TYPE_CHOICES = [
        (ASSET, "Asset"),
        (LIABILITY, "Liability"),
        (EQUITY, "Equity"),
        (REVENUE, "Revenue"),
        (EXPENSE, "Expense"),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class JournalEntry(models.Model):
    """
    Double-entry journal entry (REQ-CORE-GL-002). Immutable once posted
    (REQ-CORE-GL-008) — `post()` is the only sanctioned transition out of
    `draft`, and there is deliberately no "unpost"/edit-after-posting path;
    correcting a posted entry means posting a new reversing entry, not
    mutating history. Balance validation happens both at the serializer layer
    (JournalEntrySerializer.validate_lines, for a fast API-level rejection)
    and again here in `post()`, so nothing can reach `posted` unbalanced
    regardless of entry point (Admin, API, future AI tool-calling per
    technical.md §8.4).
    """

    DRAFT = "draft"
    POSTED = "posted"
    STATUS_CHOICES = [(DRAFT, "Draft"), (POSTED, "Posted")]

    date = models.DateField()
    memo = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="journal_entries"
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name_plural = "journal entries"

    def __str__(self) -> str:
        return f"JE#{self.id} {self.date} {self.memo}"[:60]

    def clean(self):
        if self.status == self.POSTED:
            total_debit = sum(line.debit for line in self.lines.all())
            total_credit = sum(line.credit for line in self.lines.all())
            if total_debit != total_credit:
                raise ValidationError(
                    f"Cannot post an unbalanced entry: debit {total_debit} != credit {total_credit}."
                )

    def post(self):
        """Transition draft -> posted. Raises ValidationError if unbalanced."""
        total_debit = sum(line.debit for line in self.lines.all())
        total_credit = sum(line.credit for line in self.lines.all())
        if total_debit != total_credit:
            raise ValidationError(
                f"Cannot post an unbalanced entry: debit {total_debit} != credit {total_credit}."
            )
        if not self.lines.exists():
            raise ValidationError("Cannot post an entry with no lines.")
        self.status = self.POSTED
        self.posted_at = timezone.now()
        self.save(update_fields=["status", "posted_at"])


class JournalLine(models.Model):
    """A single debit or credit line within a JournalEntry."""

    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="journal_lines")
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return f"{self.account.code} D{self.debit}/C{self.credit}"
