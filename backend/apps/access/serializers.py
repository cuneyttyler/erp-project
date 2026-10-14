from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.models import AuditLogEntry, User

from . import catalog, revert
from .models import Permission, Role, UserGrant
from .permissions import forget, is_org_admin


def _validate_codes(codes: list) -> list:
    unknown = sorted(set(codes) - catalog.grantable_codes())
    if unknown:
        raise serializers.ValidationError(f"Unknown or non-grantable actions: {', '.join(unknown)}")
    return sorted(set(codes))


class PermissionSerializer(serializers.ModelSerializer):
    actions = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    is_system = serializers.BooleanField(read_only=True)
    role_count = serializers.IntegerField(source="roles.count", read_only=True)

    class Meta:
        model = Permission
        fields = ["id", "name", "description", "actions", "system_key", "is_system", "role_count", "created_at"]
        read_only_fields = ["system_key", "created_at"]

    def validate_actions(self, value):
        return _validate_codes(value)


class RoleSerializer(serializers.ModelSerializer):
    permission_ids = serializers.PrimaryKeyRelatedField(source="permissions", queryset=Permission.objects.all(), many=True, required=False)
    is_system = serializers.BooleanField(read_only=True)
    user_count = serializers.IntegerField(source="users.count", read_only=True)

    class Meta:
        model = Role
        fields = ["id", "name", "description", "permission_ids", "grants_all", "system_key", "is_system", "user_count", "created_at"]
        read_only_fields = ["grants_all", "system_key", "created_at"]


class UserAdminSerializer(serializers.ModelSerializer):
    """A user as the administration screens see and edit one. The password
    is write-only (it never appears in a response, and so never in the
    audit trail's snapshots either)."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=False, trim_whitespace=False)
    role_ids = serializers.PrimaryKeyRelatedField(source="roles", queryset=Role.objects.all(), many=True, required=False)
    # Write-only as a field (it lives on UserGrant, not User); added to the
    # output by to_representation below.
    direct_actions = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    is_org_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "is_active",
            "preferred_locale",
            "password",
            "role_ids",
            "direct_actions",
            "is_org_admin",
            "last_login",
            "date_joined",
        ]
        read_only_fields = ["last_login", "date_joined"]

    def get_is_org_admin(self, user) -> bool:
        return is_org_admin(user)

    def to_representation(self, user):
        data = super().to_representation(user)
        grant = UserGrant.objects.filter(user=user).first()
        data["direct_actions"] = sorted(grant.actions) if grant else []
        return data

    def validate_direct_actions(self, value):
        return _validate_codes(value)

    def validate(self, attrs):
        password = attrs.get("password")
        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "A password is required for a new user."})
        if password:
            try:
                validate_password(password, self.instance)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def _save_extras(self, user, roles, direct_actions, password):
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        if roles is not None:
            user.roles.set(roles)
        if direct_actions is not None:
            UserGrant.objects.update_or_create(user=user, defaults={"actions": direct_actions})

    def create(self, validated_data):
        roles = validated_data.pop("roles", None)
        direct_actions = validated_data.pop("direct_actions", None)
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        self._save_extras(user, roles, direct_actions, None)
        return user

    def update(self, user, validated_data):
        roles = validated_data.pop("roles", None)
        direct_actions = validated_data.pop("direct_actions", None)
        password = validated_data.pop("password", None)
        user = super().update(user, validated_data)
        self._save_extras(user, roles, direct_actions, password)
        # Drop the per-request permission cache: this very response reports
        # `is_org_admin`, which must reflect the roles just saved.
        forget(user)
        return user


class AuditUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "full_name"]


def _changes(before, after) -> list[dict]:
    """The fields that differ between two snapshots, for showing "what
    changed" without shipping (or reading) both records whole."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return []
    return [
        {"field": key, "before": before.get(key), "after": after.get(key)}
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key)
    ]


class AuditLogEntrySerializer(serializers.ModelSerializer):
    user = AuditUserSerializer(read_only=True)
    resource = serializers.CharField(source="target_type", read_only=True)
    operation = serializers.SerializerMethodField()
    changes = serializers.SerializerMethodField()
    reverted_by = serializers.SerializerMethodField()
    revert = serializers.SerializerMethodField()

    class Meta:
        model = AuditLogEntry
        fields = [
            "id",
            "created_at",
            "user",
            "channel",
            "action",
            "resource",
            "operation",
            "target_id",
            "target_label",
            "changes",
            "before",
            "after",
            "reverts",
            "reverted_by",
            "revert",
        ]

    def get_operation(self, entry) -> str:
        return catalog.split_code(entry.action)[1]

    def get_changes(self, entry) -> list:
        return _changes(entry.before, entry.after)

    def get_reverted_by(self, entry):
        reverted = entry.reverted_by_entries.order_by("id").first()
        return reverted.id if reverted else None

    def get_revert(self, entry) -> dict:
        return revert.status(entry, self.context["request"].user)
