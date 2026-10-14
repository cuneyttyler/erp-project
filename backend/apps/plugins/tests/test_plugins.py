"""Tests for the plugin catalog (install/remove, licensing, who may manage
it) and the per-user home-panel layout."""

from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.access.models import UserGrant
from apps.access.permissions import forget
from apps.core.models import AuditLogEntry, User
from apps.plugins import registry
from apps.plugins.models import DashboardWidgetSetting, PluginState

HOST = {"HTTP_HOST": "tenant.test.com"}


class PluginTestBase(TenantTestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="x", is_superuser=True)
        self.member = User.objects.create_user(username="member", password="x")
        self.client = APIClient()
        self.tenant.active_packages = ["inventory", "pos"]
        self.tenant.save()

    def plugins(self):
        response = self.client.get("/api/v1/plugins/", **HOST)
        self.assertEqual(response.status_code, 200)
        return {p["key"]: p for p in response.data["plugins"]}


class PluginCatalogTests(PluginTestBase):
    def test_requires_authentication(self):
        self.assertEqual(self.client.get("/api/v1/plugins/", **HOST).status_code, 403)

    def test_core_plugins_are_always_licensed_and_packages_follow_the_subscription(self):
        self.client.force_authenticate(user=self.member)
        plugins = self.plugins()
        self.assertEqual(set(plugins), {p.key for p in registry.PLUGINS})
        self.assertTrue(plugins["general_ledger"]["is_active"])
        self.assertTrue(plugins["inventory"]["is_active"])
        # Not in active_packages: installed by default, but not usable.
        self.assertFalse(plugins["manufacturing"]["is_licensed"])
        self.assertFalse(plugins["manufacturing"]["is_active"])

    def test_can_manage_reflects_admin_status(self):
        self.client.force_authenticate(user=self.member)
        self.assertFalse(self.client.get("/api/v1/plugins/", **HOST).data["can_manage"])
        self.client.force_authenticate(user=self.admin)
        self.assertTrue(self.client.get("/api/v1/plugins/", **HOST).data["can_manage"])


class PluginToggleTests(PluginTestBase):
    def toggle(self, key, is_enabled):
        return self.client.patch(f"/api/v1/plugins/{key}/", {"is_enabled": is_enabled}, format="json", **HOST)

    def test_admin_can_remove_and_reinstall_a_plugin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.toggle("inventory", False)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_active"])
        self.assertFalse(self.plugins()["inventory"]["is_enabled"])

        response = self.toggle("inventory", True)
        self.assertTrue(response.data["is_active"])
        self.assertEqual(PluginState.objects.filter(key="inventory").count(), 1)

    def test_core_plugins_are_removable_too(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.toggle("general_ledger", False).status_code, 200)
        self.assertFalse(self.plugins()["general_ledger"]["is_active"])

    def test_non_admin_cannot_toggle(self):
        self.client.force_authenticate(user=self.member)
        self.assertEqual(self.toggle("inventory", False).status_code, 403)
        self.assertFalse(PluginState.objects.exists())

    def test_cannot_install_a_plugin_outside_the_subscription(self):
        self.client.force_authenticate(user=self.admin)
        PluginState.objects.create(key="manufacturing", is_enabled=False)
        self.assertEqual(self.toggle("manufacturing", True).status_code, 400)

    def test_unknown_plugin_is_404(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.toggle("nope", False).status_code, 404)

    def test_toggle_is_audited_once_per_actual_change(self):
        self.client.force_authenticate(user=self.admin)
        self.toggle("inventory", False)
        self.toggle("inventory", False)
        entries = AuditLogEntry.objects.filter(target_type="plugin", target_id="inventory")
        self.assertEqual([e.action for e in entries], ["plugin.remove"])
        self.assertEqual(entries[0].actor, f"user:{self.admin.id}")


class WidgetLayoutTests(PluginTestBase):
    def widgets(self):
        response = self.client.get("/api/v1/plugins/widgets/", **HOST)
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_default_layout_follows_registry_order_and_defaults(self):
        self.client.force_authenticate(user=self.member)
        widgets = self.widgets()
        self.assertEqual([w["key"] for w in widgets], [w.key for w in registry.all_widgets()])
        by_key = {w["key"]: w for w in widgets}
        self.assertTrue(by_key["attention"]["is_enabled"])
        self.assertFalse(by_key["ap_aging"]["is_enabled"])
        self.assertEqual(by_key["cash_position"]["size"], "sm")

    def test_plugin_widgets_need_a_view_permission_in_that_plugin(self):
        self.client.force_authenticate(user=self.member)
        by_key = {w["key"]: w for w in self.widgets()}
        self.assertTrue(by_key["attention"]["is_available"])  # system widget
        self.assertFalse(by_key["low_stock"]["is_available"])
        self.assertEqual(self.client.get("/api/v1/plugins/widgets/low_stock/data/", **HOST).status_code, 403)

        UserGrant.objects.create(user=self.member, actions=["stock_level.view"])
        forget(self.member)  # the test reuses this object across requests
        self.assertTrue({w["key"]: w for w in self.widgets()}["low_stock"]["is_available"])

    def test_availability_follows_the_widgets_plugin(self):
        self.client.force_authenticate(user=self.admin)
        by_key = {w["key"]: w for w in self.widgets()}
        self.assertTrue(by_key["attention"]["is_available"])  # system widget
        self.assertTrue(by_key["low_stock"]["is_available"])  # inventory is licensed
        self.assertFalse(by_key["headcount"]["is_available"])  # hr_payroll is not

        PluginState.objects.create(key="inventory", is_enabled=False)
        by_key = {w["key"]: w for w in self.widgets()}
        self.assertFalse(by_key["low_stock"]["is_available"])

    def test_saving_a_layout_sets_order_visibility_and_size(self):
        self.client.force_authenticate(user=self.member)
        layout = [
            {"key": "ar_aging", "is_enabled": True, "size": "lg"},
            {"key": "attention", "is_enabled": False, "size": "md"},
        ]
        response = self.client.put("/api/v1/plugins/widgets/layout/", {"widgets": layout}, format="json", **HOST)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([w["key"] for w in response.data[:2]], ["ar_aging", "attention"])
        self.assertEqual(response.data[0]["size"], "lg")
        self.assertFalse(response.data[1]["is_enabled"])
        # Widgets left out of the saved layout keep their defaults, after it.
        self.assertEqual(response.data[2]["key"], "cash_position")

    def test_layout_is_per_user(self):
        self.client.force_authenticate(user=self.member)
        self.client.put(
            "/api/v1/plugins/widgets/layout/", {"widgets": [{"key": "attention", "is_enabled": False, "size": "md"}]}, format="json", **HOST
        )
        self.client.force_authenticate(user=self.admin)
        self.assertTrue({w["key"]: w for w in self.widgets()}["attention"]["is_enabled"])

    def test_layout_rejects_unknown_and_duplicate_widgets(self):
        self.client.force_authenticate(user=self.member)
        for layout in (
            [{"key": "nope", "is_enabled": True, "size": "md"}],
            [{"key": "attention", "is_enabled": True, "size": "md"}] * 2,
            [{"key": "attention", "is_enabled": True, "size": "huge"}],
        ):
            response = self.client.put("/api/v1/plugins/widgets/layout/", {"widgets": layout}, format="json", **HOST)
            self.assertEqual(response.status_code, 400)
        self.assertFalse(DashboardWidgetSetting.objects.exists())

    def test_reset_restores_defaults(self):
        self.client.force_authenticate(user=self.member)
        self.client.put(
            "/api/v1/plugins/widgets/layout/", {"widgets": [{"key": "attention", "is_enabled": False, "size": "md"}]}, format="json", **HOST
        )
        response = self.client.post("/api/v1/plugins/widgets/layout/reset/", **HOST)
        self.assertEqual(response.status_code, 200)
        self.assertTrue({w["key"]: w for w in response.data}["attention"]["is_enabled"])
        self.assertFalse(DashboardWidgetSetting.objects.exists())
