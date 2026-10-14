"""Tests for roles/permissions: the catalog, enforcement on real endpoints,
the administration API, and the safeguards around it."""

from rest_framework.test import APIClient

from apps.access import catalog, defaults
from apps.access.models import Permission, Role, UserGrant
from apps.access.permissions import effective_codes, forget
from apps.access.tests.base import HOST, SharedTenantTestCase
from apps.core.models import Item, User
from apps.plugins.models import PluginState
from apps.plugins.registry import PLUGINS

ALL_PACKAGES = [p.package for p in PLUGINS if p.package]


class AccessTestBase(SharedTenantTestCase):
    def setUp(self):
        self.tenant.active_packages = ALL_PACKAGES
        self.tenant.save()
        self.admin = User.objects.create_superuser(username="root", password="x")
        self.member = User.objects.create_user(username="member", password="x")
        self.client = APIClient()

    def as_user(self, user):
        self.client.force_authenticate(user=user)
        return self.client

    def grant(self, user, *codes):
        UserGrant.objects.update_or_create(user=user, defaults={"actions": list(codes)})
        forget(user)  # the test reuses this object across requests


class CatalogTests(AccessTestBase):
    def test_operations_are_read_off_the_views(self):
        invoice = catalog.get_resource("invoice")
        self.assertEqual(set(invoice.operations), {"view", "create", "update", "delete", "send_document"})
        self.assertEqual(invoice.operations["view"].kind, catalog.READ)
        self.assertEqual(invoice.operations["send_document"].kind, catalog.WRITE)
        # A report is view-only; a read-only viewset has no write operations
        # beyond its explicit actions.
        self.assertEqual(set(catalog.get_resource("trial_balance").operations), {"view"})
        self.assertEqual(set(catalog.get_resource("pos_sale").operations), {"view", "return_sale"})
        # A GET-only extra endpoint (the Z-report) is covered by "view".
        self.assertNotIn("z_report", catalog.get_resource("pos_shift").operations)

    def test_every_resource_belongs_to_a_known_plugin_or_is_admin_only(self):
        plugin_keys = {p.key for p in PLUGINS}
        for res in catalog.all_resources():
            with self.subTest(resource=res.key):
                self.assertTrue(res.admin_only or res.plugin in plugin_keys)
                self.assertTrue(res.operations)

    def test_administration_and_open_actions_are_not_grantable(self):
        grantable = catalog.grantable_codes()
        self.assertIn("invoice.create", grantable)
        self.assertNotIn("user.update", grantable)
        self.assertNotIn("role.create", grantable)
        self.assertNotIn("entity.view", grantable)


class EnforcementTests(AccessTestBase):
    def test_a_user_with_no_grants_is_refused(self):
        self.assertEqual(self.as_user(self.member).get("/api/v1/core/items/", **HOST).status_code, 403)

    def test_view_grant_allows_reading_but_not_writing(self):
        self.grant(self.member, "item.view")
        client = self.as_user(self.member)
        self.assertEqual(client.get("/api/v1/core/items/", **HOST).status_code, 200)
        response = client.post("/api/v1/core/items/", {"sku": "A", "name": "A"}, format="json", **HOST)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Item.objects.exists())

    def test_each_operation_needs_its_own_action(self):
        item = Item.objects.create(sku="A", name="A")
        self.grant(self.member, "item.view", "item.update")
        client = self.as_user(self.member)
        self.assertEqual(client.patch(f"/api/v1/core/items/{item.id}/", {"name": "B"}, format="json", **HOST).status_code, 200)
        self.assertEqual(client.delete(f"/api/v1/core/items/{item.id}/", **HOST).status_code, 403)

    def test_custom_actions_are_guarded_separately(self):
        self.grant(self.member, "journal_entry.view", "journal_entry.create")
        response = self.as_user(self.member).post("/api/v1/core/journal-entries/1/post_entry/", **HOST)
        self.assertEqual(response.status_code, 403)

    def test_reports_are_guarded(self):
        client = self.as_user(self.member)
        self.assertEqual(client.get("/api/v1/core/reports/ar-aging/", **HOST).status_code, 403)
        self.grant(self.member, "ar_aging.view")
        self.assertEqual(client.get("/api/v1/core/reports/ar-aging/", **HOST).status_code, 200)

    def test_open_operations_need_no_grant(self):
        client = self.as_user(self.member)
        self.assertEqual(client.get("/api/v1/core/entities/", **HOST).status_code, 200)
        self.assertEqual(client.post("/api/v1/core/entities/", {"name": "X", "code": "X"}, format="json", **HOST).status_code, 403)

    def test_package_licensing_still_applies_on_top(self):
        self.grant(self.member, "warehouse.view")
        self.tenant.active_packages = []
        self.tenant.save()
        self.assertEqual(self.as_user(self.member).get("/api/v1/inventory/warehouses/", **HOST).status_code, 403)

    def test_grants_through_a_role_and_its_permissions(self):
        permission = Permission.objects.create(name="Catalog editing", actions=["item.view", "item.create"])
        role = Role.objects.create(name="Catalog editor")
        role.permissions.add(permission)
        role.users.add(self.member)
        client = self.as_user(self.member)
        self.assertEqual(client.post("/api/v1/core/items/", {"sku": "A", "name": "A"}, format="json", **HOST).status_code, 201)

    def test_the_admin_role_grants_everything_including_administration(self):
        defaults.ensure_defaults()
        Role.objects.get(system_key=defaults.ORG_ADMIN).users.add(self.member)
        client = self.as_user(self.member)
        self.assertEqual(client.get("/api/v1/core/items/", **HOST).status_code, 200)
        self.assertEqual(client.get("/api/v1/access/users/", **HOST).status_code, 200)


class SessionPayloadTests(AccessTestBase):
    def me(self, user):
        return self.as_user(user).get("/api/v1/core/auth/me/", **HOST).data["access"]

    def test_reports_effective_actions(self):
        self.grant(self.member, "item.view")
        access = self.me(self.member)
        self.assertFalse(access["is_org_admin"])
        self.assertEqual(sorted(access["actions"]), ["entity.view", "item.view"])

    def test_admin_holds_every_action(self):
        access = self.me(self.admin)
        self.assertTrue(access["is_org_admin"])
        self.assertIn("user.create", access["actions"])
        self.assertIn("invoice.send_document", access["actions"])

    def test_actions_of_a_removed_or_unlicensed_plugin_are_withheld(self):
        self.grant(self.member, "item.view", "warehouse.view")
        PluginState.objects.create(key="item_catalog", is_enabled=False)
        self.tenant.active_packages = []
        self.tenant.save()
        self.assertEqual(effective_codes(self.member, self.tenant), ["entity.view"])
        self.assertNotIn("warehouse.view", self.me(self.admin)["actions"])


class BuiltInDefaultsTests(AccessTestBase):
    def test_creates_admin_viewer_and_per_plugin_permissions(self):
        defaults.ensure_defaults()
        self.assertTrue(Role.objects.get(system_key=defaults.ORG_ADMIN).grants_all)
        view = Permission.objects.get(system_key=defaults.view_key("receivables_payables"))
        manage = Permission.objects.get(system_key=defaults.manage_key("receivables_payables"))
        self.assertIn("invoice.view", view.actions)
        self.assertNotIn("invoice.create", view.actions)
        self.assertIn("invoice.send_document", manage.actions)
        viewer = Role.objects.get(system_key=defaults.VIEWER)
        self.assertEqual(viewer.permissions.count(), Permission.objects.filter(system_key__endswith=":view").count())

    def test_a_plugins_permissions_include_viewing_what_its_screens_look_up(self):
        defaults.ensure_defaults()
        purchasing = Permission.objects.get(system_key=defaults.manage_key("purchasing"))
        for code in ("party.view", "item.view", "warehouse.view"):
            self.assertIn(code, purchasing.actions)

    def test_is_idempotent_and_repairs_drift(self):
        defaults.ensure_defaults()
        count = Permission.objects.count()
        permission = Permission.objects.get(system_key=defaults.view_key("general_ledger"))
        permission.actions = []
        permission.save()
        defaults.ensure_defaults()
        permission.refresh_from_db()
        self.assertIn("account.view", permission.actions)
        self.assertEqual(Permission.objects.count(), count)

    def test_viewer_role_can_read_but_not_write(self):
        defaults.ensure_defaults()
        Role.objects.get(system_key=defaults.VIEWER).users.add(self.member)
        client = self.as_user(self.member)
        self.assertEqual(client.get("/api/v1/core/invoices/", **HOST).status_code, 200)
        self.assertEqual(client.post("/api/v1/core/items/", {"sku": "A", "name": "A"}, format="json", **HOST).status_code, 403)


class AdministrationApiTests(AccessTestBase):
    def test_only_admins_reach_the_administration_api(self):
        client = self.as_user(self.member)
        for path in ("users", "roles", "permissions"):
            self.assertEqual(client.get(f"/api/v1/access/{path}/", **HOST).status_code, 403)

    def test_action_catalog_lists_grantable_actions_by_group(self):
        response = self.as_user(self.member).get("/api/v1/access/actions/", **HOST)
        self.assertEqual(response.status_code, 200)
        groups = {g["group"]: g for g in response.data}
        self.assertNotIn(catalog.ADMINISTRATION, groups)
        ledger = {r["key"]: r for r in groups["general_ledger"]["resources"]}
        self.assertIn("journal_entry.post_entry", [o["code"] for o in ledger["journal_entry"]["operations"]])

    def test_create_permission_role_and_assign_to_a_new_user(self):
        client = self.as_user(self.admin)
        permission = client.post(
            "/api/v1/access/permissions/", {"name": "Invoicing", "actions": ["invoice.view", "invoice.create"]}, format="json", **HOST
        )
        self.assertEqual(permission.status_code, 201, permission.data)
        role = client.post("/api/v1/access/roles/", {"name": "Billing clerk", "permission_ids": [permission.data["id"]]}, format="json", **HOST)
        self.assertEqual(role.status_code, 201, role.data)
        user = client.post(
            "/api/v1/access/users/",
            {"username": "ayse", "password": "a-Long-passphrase-9", "role_ids": [role.data["id"]], "direct_actions": ["party.view"]},
            format="json",
            **HOST,
        )
        self.assertEqual(user.status_code, 201, user.data)
        self.assertNotIn("password", user.data)
        self.assertEqual(user.data["direct_actions"], ["party.view"])

        ayse = User.objects.get(username="ayse")
        self.assertTrue(ayse.check_password("a-Long-passphrase-9"))
        self.assertEqual(sorted(effective_codes(ayse, self.tenant)), ["entity.view", "invoice.create", "invoice.view", "party.view"])

    def test_rejects_unknown_and_administration_actions(self):
        client = self.as_user(self.admin)
        for actions in (["nope.view"], ["user.update"], ["entity.view"]):
            response = client.post("/api/v1/access/permissions/", {"name": "X", "actions": actions}, format="json", **HOST)
            self.assertEqual(response.status_code, 400)

    def test_new_user_needs_an_acceptable_password(self):
        client = self.as_user(self.admin)
        self.assertEqual(client.post("/api/v1/access/users/", {"username": "a"}, format="json", **HOST).status_code, 400)
        self.assertEqual(client.post("/api/v1/access/users/", {"username": "a", "password": "123"}, format="json", **HOST).status_code, 400)
        self.assertFalse(User.objects.filter(username="a").exists())

    def test_built_in_records_cannot_be_edited_or_deleted(self):
        client = self.as_user(self.admin)
        client.get("/api/v1/access/roles/", **HOST)  # creates the defaults
        viewer = Role.objects.get(system_key=defaults.VIEWER)
        permission = Permission.objects.filter(system_key__isnull=False).first()
        self.assertEqual(client.patch(f"/api/v1/access/roles/{viewer.id}/", {"name": "x"}, format="json", **HOST).status_code, 403)
        self.assertEqual(client.delete(f"/api/v1/access/roles/{viewer.id}/", **HOST).status_code, 403)
        self.assertEqual(client.delete(f"/api/v1/access/permissions/{permission.id}/", **HOST).status_code, 403)

    def test_users_cannot_be_deleted_only_deactivated(self):
        client = self.as_user(self.admin)
        self.assertEqual(client.delete(f"/api/v1/access/users/{self.member.id}/", **HOST).status_code, 405)
        self.assertEqual(client.patch(f"/api/v1/access/users/{self.member.id}/", {"is_active": False}, format="json", **HOST).status_code, 200)

    def test_cannot_deactivate_yourself(self):
        response = self.as_user(self.admin).patch(f"/api/v1/access/users/{self.admin.id}/", {"is_active": False}, format="json", **HOST)
        self.assertEqual(response.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_the_last_admin_cannot_be_removed(self):
        defaults.ensure_defaults()
        admin_role = Role.objects.get(system_key=defaults.ORG_ADMIN)
        only_admin = User.objects.create_user(username="only", password="x")
        admin_role.users.add(only_admin)
        self.admin.is_superuser = False
        self.admin.save()

        client = self.as_user(only_admin)
        response = client.patch(f"/api/v1/access/users/{only_admin.id}/", {"role_ids": []}, format="json", **HOST)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(admin_role.users.filter(id=only_admin.id).exists())  # rolled back

        # With a second admin in place, stepping down is fine.
        admin_role.users.add(self.member)
        response = client.patch(f"/api/v1/access/users/{only_admin.id}/", {"role_ids": []}, format="json", **HOST)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_org_admin"])
