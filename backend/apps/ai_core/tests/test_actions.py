"""Registry behavior tests for the write-action registry (technical.md
§8.4), mirroring test_semantic.py's shape exactly. Uses throwaway action
names (prefixed `_test_`) so these don't collide with the real actions
every package's ai_tools.py registers at app startup."""

from django.test import SimpleTestCase

from apps.ai_core import actions


class ActionRegistryTests(SimpleTestCase):
    def test_registered_action_with_no_package_is_always_available(self):
        actions.register_action(
            name="_test_always_on_action", description="test", input_schema={"type": "object", "properties": {}}
        )(lambda user, **kw: {"result": {}})

        self.assertIn("_test_always_on_action", [a.name for a in actions.available_actions([])])
        self.assertIn("_test_always_on_action", [a.name for a in actions.available_actions(["inventory"])])

    def test_registered_action_with_package_requires_that_package(self):
        actions.register_action(
            name="_test_gated_action",
            description="test",
            input_schema={"type": "object", "properties": {}},
            package="manufacturing",
        )(lambda user, **kw: {"result": {}})

        self.assertNotIn("_test_gated_action", [a.name for a in actions.available_actions([])])
        self.assertIn("_test_gated_action", [a.name for a in actions.available_actions(["manufacturing"])])

    def test_get_action_returns_none_for_ungranted_package(self):
        actions.register_action(
            name="_test_get_gated_action",
            description="test",
            input_schema={"type": "object", "properties": {}},
            package="hr_payroll",
        )(lambda user, **kw: {"result": {"ok": True}})

        self.assertIsNone(actions.get_action("_test_get_gated_action", []))
        self.assertIsNotNone(actions.get_action("_test_get_gated_action", ["hr_payroll"]))

    def test_get_action_returns_none_for_unknown_name(self):
        self.assertIsNone(actions.get_action("_test_does_not_exist", ["inventory"]))

    def test_default_preview_includes_description_and_params(self):
        action = actions.register_action(
            name="_test_preview_action", description="Does a thing.", input_schema={"type": "object", "properties": {}}
        )(lambda user, **kw: {"result": {}})
        preview = actions.default_preview(actions.get_action("_test_preview_action", []), {"x": 1})
        self.assertIn("Does a thing.", preview)
        self.assertIn("'x': 1", preview)

    def test_custom_preview_is_used_when_provided(self):
        actions.register_action(
            name="_test_custom_preview_action",
            description="test",
            input_schema={"type": "object", "properties": {}},
            preview=lambda **kw: f"Custom preview for {kw.get('thing')}",
        )(lambda user, **kw: {"result": {}})
        action = actions.get_action("_test_custom_preview_action", [])
        self.assertEqual(action.preview(thing="widget"), "Custom preview for widget")

    def test_real_actions_are_registered_at_startup(self):
        # Sanity check that CoreConfig/HrPayrollConfig.ready() actually ran
        # and imported each package's ai_tools.py -- a regression test for
        # the app-startup wiring itself, not just the registry's own logic.
        names = [a.name for a in actions.available_actions(["hr_payroll"])]
        self.assertIn("create_journal_entry", names)
        self.assertIn("approve_leave_request", names)
