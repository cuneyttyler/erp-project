from rest_framework import serializers

from .models import Account, JournalEntry, JournalLine, Role, User


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
    class Meta:
        model = Account
        fields = ["id", "code", "name", "account_type", "parent", "is_active"]


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

    class Meta:
        model = JournalEntry
        fields = [
            "id",
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

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        request = self.context.get("request")
        entry = JournalEntry.objects.create(
            created_by=request.user if request else None, **validated_data
        )
        for line_data in lines_data:
            JournalLine.objects.create(journal_entry=entry, **line_data)
        return entry
