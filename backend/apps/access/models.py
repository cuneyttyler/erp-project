"""
Who may do what (REQ-CORE-USR-002/003).

The chain is: an *action* (a code from catalog.py, defined in code) is put in
a `Permission`; permissions are put in a `Role`; roles are given to users.
A user can also be granted individual actions directly (`UserGrant`), for the
one-off case that doesn't deserve a role of its own. What a user can do is
the union of all of it -- there is no "deny" rule to reason about.
"""

from django.conf import settings
from django.db import models


class Permission(models.Model):
    """A named bundle of actions, e.g. "Invoicing" = create/update/send
    invoices + view customers. `actions` holds catalog codes as strings --
    the catalog is code-defined, so there is no table to point a FK at; a
    code whose action has since been removed from the app simply stops
    matching anything."""

    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    actions = models.JSONField(default=list, blank=True)
    # Set on the built-in permissions (one "view" and one "full access" per
    # plugin, see defaults.py), which are kept in step with the catalog
    # automatically and can't be edited or deleted. Null for everything an
    # admin creates.
    system_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def is_system(self) -> bool:
        return self.system_key is not None


class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="roles", blank=True)
    # The organization-admin role: holds every action, present and future,
    # and is the only way (besides being a Django superuser) to use the
    # administration area. Exactly one such role exists per tenant.
    grants_all = models.BooleanField(default=False)
    system_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def is_system(self) -> bool:
        return self.system_key is not None


class UserGrant(models.Model):
    """Actions granted to one user directly, outside any role."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="direct_grant")
    actions = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return f"{self.user}: {len(self.actions)} direct actions"
