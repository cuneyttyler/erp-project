"""
The built-in roles and permissions every tenant starts with, so an admin
has something sensible to hand out on day one instead of an empty editor:

- the **Organization Admin** role (holds everything);
- for each plugin, a **View** permission (its read actions) and a **Full
  access** permission (all of its actions); and
- a **Viewer** role holding every plugin's View permission.

They're derived from the action catalog rather than stored once: each time
the administration API is used, `ensure_defaults()` brings them back in
step, so an action added to the app later joins the right built-in
permission without a data migration. That's also why they're read-only in
the UI -- a manual edit would just be overwritten.
"""

from apps.plugins.registry import PLUGINS

from . import catalog
from .models import Permission, Role

ORG_ADMIN = "org_admin"
VIEWER = "viewer"

# Screens in one plugin look up records that belong to another (a purchase
# order picks a vendor, an item and a warehouse). A plugin's built-in
# permissions include *viewing* those, or the role would open the page and
# then fail to fill its dropdowns.
REFERENCE_VIEWS = {
    "inventory": ["item.view"],
    "purchasing": ["item.view", "party.view", "warehouse.view"],
    "sales_crm": ["item.view", "party.view", "warehouse.view"],
    "manufacturing": ["item.view", "warehouse.view"],
    "pos": ["item.view", "warehouse.view"],
    "ecommerce": ["item.view", "warehouse.view"],
}


def _plugin_codes(plugin_key: str, read_only: bool) -> list[str]:
    grantable = catalog.grantable_codes()
    codes = set(code for code in REFERENCE_VIEWS.get(plugin_key, []) if code in grantable)
    for resource in catalog.grantable_resources():
        if resource.plugin != plugin_key:
            continue
        for name, operation in resource.operations.items():
            if name in resource.open_operations:
                continue
            if not read_only or operation.kind == catalog.READ:
                codes.add(resource.code(name))
    return sorted(codes)


def view_key(plugin_key: str) -> str:
    return f"plugin:{plugin_key}:view"


def manage_key(plugin_key: str) -> str:
    return f"plugin:{plugin_key}:manage"


def ensure_defaults() -> None:
    """Idempotent, and cheap when nothing changed: two reads, no writes."""
    wanted = {}
    for plugin in PLUGINS:
        view_codes = _plugin_codes(plugin.key, read_only=True)
        manage_codes = _plugin_codes(plugin.key, read_only=False)
        if not manage_codes:
            continue
        label = plugin.key.replace("_", " ").title()
        # The frontend shows a translated name from `system_key`; this
        # English one is what the API, the admin site and exports carry.
        wanted[view_key(plugin.key)] = (f"{label}: View", view_codes)
        wanted[manage_key(plugin.key)] = (f"{label}: Full access", manage_codes)

    existing = {p.system_key: p for p in Permission.objects.filter(system_key__isnull=False)}
    for key, (name, codes) in wanted.items():
        permission = existing.get(key)
        if permission is None:
            Permission.objects.create(system_key=key, name=name, actions=codes)
        elif permission.actions != codes or permission.name != name:
            permission.actions, permission.name = codes, name
            permission.save(update_fields=["actions", "name"])
    Permission.objects.filter(system_key__isnull=False).exclude(system_key__in=wanted).delete()

    Role.objects.get_or_create(
        system_key=ORG_ADMIN,
        defaults={"name": "Organization Admin", "description": "Can do everything, including managing users, roles and plugins.", "grants_all": True},
    )
    viewer, _ = Role.objects.get_or_create(
        system_key=VIEWER,
        defaults={"name": "Viewer", "description": "Can see everything in every plugin, and change nothing."},
    )
    view_ids = set(Permission.objects.filter(system_key__endswith=":view").values_list("id", flat=True))
    if set(viewer.permissions.values_list("id", flat=True)) != view_ids:
        viewer.permissions.set(view_ids)
