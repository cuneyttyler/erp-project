from rest_framework import serializers

from .models import (
    Account,
    Bill,
    BillLine,
    Entity,
    Invoice,
    InvoiceLine,
    Item,
    JournalEntry,
    JournalLine,
    Party,
    Payment,
    Role,
    SavedView,
    User,
)


class EntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Entity
        fields = ["id", "name", "code", "currency", "is_active", "created_at"]
        read_only_fields = ["created_at"]


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "granted_actions"]


class UserSerializer(serializers.ModelSerializer):
    roles = RoleSerializer(many=True, read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "preferred_locale",
            "mfa_enabled",
            "roles",
        ]


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class AccountSerializer(serializers.ModelSerializer):
    # Declared explicitly rather than via Meta.extra_kwargs: entity is
    # null=True at the DB level for migration-backfill reasons only (see
    # models.py), and DRF's ModelSerializer auto-generation adds an implicit
    # `default=None` for any null=True FK before extra_kwargs are layered on
    # top -- overriding `required=True` via extra_kwargs while that
    # leftover `default=None` is still present trips DRF's own
    # "may not set both `required` and `default`" assertion (a real 500,
    # not a hypothetical). Declaring the field directly sidesteps that
    # auto-generation path entirely.
    entity = serializers.PrimaryKeyRelatedField(queryset=Entity.objects.all())

    class Meta:
        model = Account
        fields = ["id", "entity", "code", "name", "account_type", "parent", "is_active", "is_intercompany"]


class ItemSerializer(serializers.ModelSerializer):
    """REQ-INV-001 -- lives here because Item itself is Core master data
    (models.py docstring); apps.purchasing/apps.inventory both reference it."""

    class Meta:
        model = Item
        fields = ["id", "sku", "name", "unit_of_measure", "cost_method", "is_active"]


class TrialBalanceRowSerializer(serializers.Serializer):
    """
    Explicit serializer for TrialBalanceView's aggregated rows. This matters
    more than it looks: a raw dict of Decimal aggregates handed straight to
    Response() bypasses DRF's per-field DecimalField.to_representation and
    falls back to the JSON encoder's default Decimal handling, which coerces
    to a bare float -- silently reintroducing float rounding error into a
    financial figure (the exact failure mode `technical.md` §8.1 is written
    to prevent, just at the API layer instead of the AI layer). Routing
    through a DecimalField here guarantees a fixed-precision string
    ("10000.00"), not a float, reaches the frontend.
    """

    code = serializers.CharField()
    name = serializers.CharField()
    account_type = serializers.CharField()
    total_debit = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_credit = serializers.DecimalField(max_digits=14, decimal_places=2)


class JournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = JournalLine
        fields = [
            "id",
            "account",
            "account_code",
            "account_name",
            "debit",
            "credit",
            "description",
        ]


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    # See AccountSerializer.entity's comment -- declared explicitly, not via
    # extra_kwargs, to avoid DRF's own required/default assertion.
    entity = serializers.PrimaryKeyRelatedField(queryset=Entity.objects.all())

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "entity",
            "date",
            "memo",
            "status",
            "lines",
            "created_by_username",
            "posted_at",
            "created_at",
        ]
        read_only_fields = ["status", "posted_at", "created_at"]

    def validate_lines(self, lines):
        if len(lines) < 2:
            raise serializers.ValidationError(
                "A journal entry needs at least two lines to balance (REQ-CORE-GL-002)."
            )
        total_debit = sum(line["debit"] for line in lines)
        total_credit = sum(line["credit"] for line in lines)
        if total_debit != total_credit:
            raise serializers.ValidationError(
                f"Entry does not balance: total debit {total_debit} != total credit {total_credit}."
            )
        return lines

    def validate(self, attrs):
        # REQ-CORE-ENT-001: a journal entry belongs to exactly one entity's
        # ledger -- every line's account must actually be on that entity's
        # own Chart of Accounts, not borrowed from a different entity's COA.
        entity = attrs.get("entity") or getattr(self.instance, "entity", None)
        lines = attrs.get("lines")
        if entity is not None and lines:
            mismatched = [line["account"].code for line in lines if line["account"].entity_id != entity.id]
            if mismatched:
                raise serializers.ValidationError(
                    f"Account(s) {', '.join(mismatched)} don't belong to this entity's Chart of Accounts."
                )
        return attrs

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        request = self.context.get("request")
        entry = JournalEntry.objects.create(
            created_by=request.user if request else None, **validated_data
        )
        for line_data in lines_data:
            JournalLine.objects.create(journal_entry=entry, **line_data)
        return entry


class PartySerializer(serializers.ModelSerializer):
    # See AccountSerializer.entity's comment -- declared explicitly, not via
    # extra_kwargs, to avoid DRF's own required/default assertion.
    entity = serializers.PrimaryKeyRelatedField(queryset=Entity.objects.all())

    class Meta:
        model = Party
        fields = [
            "id",
            "entity",
            "name",
            "party_type",
            "tax_id",
            "email",
            "phone",
            "payment_terms_days",
            "is_active",
        ]


class InvoiceLineSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = InvoiceLine
        fields = ["id", "description", "quantity", "unit_price", "amount"]


class InvoiceSerializer(serializers.ModelSerializer):
    """REQ-CORE-AR-001/002. `total`/`amount_paid`/`balance_due`/`is_overdue`
    are FinancialDocument properties (models.py) -- routed through explicit
    DecimalField/BooleanField here for the same reason as TrialBalanceRowSerializer:
    a bare Python Decimal/attribute handed to Response() without a serializer
    field risks the float-coercion bug, this guarantees a precise string."""

    lines = InvoiceLineSerializer(many=True)
    party_name = serializers.CharField(source="party.name", read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "party",
            "party_name",
            "issue_date",
            "due_date",
            "currency",
            "status",
            "memo",
            "lines",
            "total",
            "amount_paid",
            "balance_due",
            "is_overdue",
            "created_at",
        ]
        read_only_fields = ["status", "created_at"]

    def validate_lines(self, lines):
        if not lines:
            raise serializers.ValidationError("An invoice needs at least one line.")
        return lines

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        invoice = Invoice.objects.create(**validated_data)
        for line_data in lines_data:
            InvoiceLine.objects.create(invoice=invoice, **line_data)
        return invoice


class BillLineSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = BillLine
        fields = ["id", "description", "quantity", "unit_price", "amount"]


class BillSerializer(serializers.ModelSerializer):
    """REQ-CORE-AP-001/002 -- see InvoiceSerializer docstring for why the
    computed totals are routed through explicit fields, not returned bare."""

    lines = BillLineSerializer(many=True)
    party_name = serializers.CharField(source="party.name", read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Bill
        fields = [
            "id",
            "party",
            "party_name",
            "issue_date",
            "due_date",
            "currency",
            "status",
            "memo",
            "lines",
            "total",
            "amount_paid",
            "balance_due",
            "is_overdue",
            "created_at",
        ]
        read_only_fields = ["status", "created_at"]

    def validate_lines(self, lines):
        if not lines:
            raise serializers.ValidationError("A bill needs at least one line.")
        return lines

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        bill = Bill.objects.create(**validated_data)
        for line_data in lines_data:
            BillLine.objects.create(bill=bill, **line_data)
        return bill


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "invoice", "bill", "amount", "date", "method", "created_at"]
        read_only_fields = ["created_at"]

    def validate(self, data):
        # Partial updates (PATCH) may omit one side -- fall back to the
        # existing instance's value so the exactly-one-of check still holds.
        invoice = data.get("invoice", getattr(self.instance, "invoice", None))
        bill = data.get("bill", getattr(self.instance, "bill", None))
        if bool(invoice) == bool(bill):
            raise serializers.ValidationError(
                "A payment must apply to exactly one of invoice or bill."
            )
        return data


class SavedViewSerializer(serializers.ModelSerializer):
    """REQ-CORE-UX-003. `owner` is read-only here -- always forced to
    `request.user` by the view on create, never client-supplied, so a user
    can't save a view under someone else's name."""

    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = SavedView
        fields = [
            "id",
            "screen_key",
            "name",
            "owner",
            "owner_username",
            "is_shared",
            "is_default",
            "config",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["owner", "created_at", "updated_at"]


class AgingRowSerializer(serializers.Serializer):
    """
    AR/AP aging report rows (REQ-CORE-AR-003/REQ-CORE-AP-002) -- same
    discipline as TrialBalanceRowSerializer: balance_due must serialize as a
    precise decimal string, never a bare float (technical.md §8.1).
    """

    document_id = serializers.IntegerField()
    party_name = serializers.CharField()
    due_date = serializers.DateField()
    balance_due = serializers.DecimalField(max_digits=14, decimal_places=2)
    days_overdue = serializers.IntegerField()
    bucket = serializers.CharField()
