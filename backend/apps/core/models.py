from decimal import Decimal

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


class Item(models.Model):
    """
    Product/service master data (REQ-INV-001). Lives in Core, not
    apps.inventory, because technical.md §5 explicitly calls it out as
    "shared by Inventory, Purchasing, Sales, Manufacturing" -- multiple
    packages need to reference it via FK, and the cross-app rule
    (technical.md §4: packages may depend on core, never reach into each
    other's internals) only works cleanly if the genuinely shared entities
    actually live in core rather than in whichever package happened to need
    it first.
    """

    FIFO = "fifo"
    WEIGHTED_AVERAGE = "weighted_average"
    COST_METHOD_CHOICES = [(FIFO, "FIFO"), (WEIGHTED_AVERAGE, "Weighted Average")]

    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    unit_of_measure = models.CharField(max_length=20, default="adet")
    cost_method = models.CharField(max_length=20, choices=COST_METHOD_CHOICES, default=WEIGHTED_AVERAGE)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sku"]

    def __str__(self) -> str:
        return f"{self.sku} — {self.name}"


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


class Party(models.Model):
    """
    Unified Customer/Vendor record (technical.md §5 `Party`). Unified base to
    avoid duplicating near-identical entities between AR and AP -- the same
    company is often both a customer and a vendor to a Turkish SME.
    """

    CUSTOMER = "customer"
    VENDOR = "vendor"
    BOTH = "both"
    PARTY_TYPE_CHOICES = [(CUSTOMER, "Customer"), (VENDOR, "Vendor"), (BOTH, "Both")]

    name = models.CharField(max_length=255)
    party_type = models.CharField(max_length=10, choices=PARTY_TYPE_CHOICES, default=CUSTOMER)
    # VKN (10 digits) or TCKN (11 digits) -- checksum validation (REQ-DATA-003)
    # belongs to the migration/onboarding import path, not free-form entry here.
    tax_id = models.CharField(max_length=11, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    payment_terms_days = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class FinancialDocument(models.Model):
    """
    Shared shape and status lifecycle for AR Invoices and AP Bills -- both are
    "a party owes/is owed money, itemized in lines, tracked through a status
    lifecycle." Abstract, not a concrete model: Invoice (REQ-CORE-AR-001/002)
    and Bill (REQ-CORE-AP-001) stay separate tables so "everything my
    customers owe me" and "everything I owe vendors" are independently
    queryable, without duplicating the shape or the status machine twice.

    `total`/`amount_paid`/`balance_due` are computed in Python over prefetched
    related rows, not via SQL Sum() annotations joining `lines` and `payments`
    simultaneously -- that join would fan out and silently double-count both
    sums. This is the same class of correctness bug as the trial-balance float
    issue (technical.md §8.1), just via join fan-out instead of type coercion;
    worth the extra Python loop to not risk it on a financial total.
    """

    DRAFT = "draft"
    SENT = "sent"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (SENT, "Sent"),
        (PARTIALLY_PAID, "Partially Paid"),
        (PAID, "Paid"),
        (CANCELLED, "Cancelled"),
    ]

    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name="%(class)ss")
    issue_date = models.DateField()
    due_date = models.DateField()
    currency = models.CharField(max_length=3, default="TRY")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    memo = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-issue_date", "-id"]

    @property
    def total(self):
        return sum((line.amount for line in self.lines.all()), Decimal("0"))

    @property
    def amount_paid(self):
        return sum((p.amount for p in self.payments.all()), Decimal("0"))

    @property
    def balance_due(self):
        return self.total - self.amount_paid

    @property
    def is_overdue(self):
        return self.status in (self.SENT, self.PARTIALLY_PAID) and self.due_date < timezone.localdate()

    def mark_sent(self):
        if self.status != self.DRAFT:
            raise ValidationError("Only a draft document can be marked as sent.")
        if not self.lines.exists():
            raise ValidationError("Cannot send a document with no lines.")
        self.status = self.SENT
        self.save(update_fields=["status"])

    def recompute_status(self):
        """
        Called after any payment is recorded against this document
        (REQ-CORE-AR-002 partial payments). A draft or cancelled document is
        never auto-transitioned -- only `mark_sent()` (human/API-initiated)
        moves a draft forward, and cancellation is a deliberate terminal state.
        """
        if self.status in (self.DRAFT, self.CANCELLED):
            return
        balance = self.balance_due
        if balance <= 0:
            new_status = self.PAID
        elif self.amount_paid > 0:
            new_status = self.PARTIALLY_PAID
        else:
            new_status = self.SENT
        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=["status"])


class Invoice(FinancialDocument):
    """Customer invoice (AR) -- REQ-CORE-AR-001/002/003."""

    def __str__(self) -> str:
        return f"INV-{self.id} {self.party.name}"


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)

    @property
    def amount(self):
        return self.quantity * self.unit_price

    def __str__(self) -> str:
        return f"{self.description} x{self.quantity}"


class Bill(FinancialDocument):
    """Vendor bill (AP) -- REQ-CORE-AP-001/002."""

    def __str__(self) -> str:
        return f"BILL-{self.id} {self.party.name}"


class BillLine(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)

    @property
    def amount(self):
        return self.quantity * self.unit_price

    def __str__(self) -> str:
        return f"{self.description} x{self.quantity}"


class Payment(models.Model):
    """
    A payment applied against either an Invoice (money received, AR) or a
    Bill (money paid, AP) -- REQ-CORE-AR-002/REQ-CORE-AP-002. Modeled as two
    nullable FKs (exactly one must be set, enforced in clean()) rather than a
    generic relation: there are only ever two possible targets, and a generic
    FK would only make querying harder for no real flexibility gained.
    """

    invoice = models.ForeignKey(
        Invoice, null=True, blank=True, on_delete=models.CASCADE, related_name="payments"
    )
    bill = models.ForeignKey(
        Bill, null=True, blank=True, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField()
    method = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def clean(self):
        if bool(self.invoice_id) == bool(self.bill_id):
            raise ValidationError("A payment must apply to exactly one of invoice or bill.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        target = self.invoice or self.bill
        target.recompute_status()

    def __str__(self) -> str:
        target = self.invoice or self.bill
        return f"Payment {self.amount} -> {target}"


class SavedView(models.Model):
    """
    A saved column configuration ("variant") for one data-table screen
    (REQ-CORE-UX-003, from direct user feedback -- docs/feedback.md
    "Feedback 1": one user wants columns a/b/c wide, another wants a/b/d/f
    narrow, both should be able to save and switch back to their own
    layout without reconfiguring it every visit).

    `screen_key` identifies which screen this belongs to (e.g. "items",
    "invoices") -- a free-text key rather than an enum/FK, since new
    screens adopting DataTable.vue shouldn't require a migration to
    register. `config` holds the whole view state (column order/
    visibility/widths, sort, filters) as one JSON blob rather than
    normalized columns -- the frontend owns that shape entirely; the
    backend only stores and scopes it, it never reads inside it.

    Personal vs. shared (`is_shared`): a personal view is only visible to
    its owner; a shared view is visible to every user on the tenant.
    Editing/deleting is restricted to the creator either way (see
    SavedViewViewSet) -- there's no view-level ACL beyond that in this
    pass, same "known gap, flagged not hidden" discipline as every other
    field-level-permission shortcut already noted elsewhere in this
    codebase (e.g. EmployeeViewSet's docstring).
    """

    screen_key = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_views"
    )
    is_shared = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    config = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["screen_key", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["screen_key", "owner", "name"], name="unique_saved_view_name_per_owner_screen"
            )
        ]

    def __str__(self) -> str:
        return f"{self.screen_key}:{self.name} ({'shared' if self.is_shared else self.owner})"
