"""Registry behavior tests (technical.md §8.2). Uses throwaway metric names
(prefixed `_test_`) so these tests don't collide with or depend on the real
metrics registered by every package's ai_tools.py at app startup."""

from django.test import SimpleTestCase

from apps.ai_core import semantic


class MetricRegistryTests(SimpleTestCase):
    def test_registered_metric_with_no_package_is_always_available(self):
        semantic.register_metric(
            name="_test_always_on", description="test", input_schema={"type": "object", "properties": {}}
        )(lambda **kw: {"result": {}, "citations": []})

        self.assertIn("_test_always_on", [m.name for m in semantic.available_metrics([])])
        self.assertIn("_test_always_on", [m.name for m in semantic.available_metrics(["inventory"])])

    def test_registered_metric_with_package_requires_that_package(self):
        semantic.register_metric(
            name="_test_gated",
            description="test",
            input_schema={"type": "object", "properties": {}},
            package="manufacturing",
        )(lambda **kw: {"result": {}, "citations": []})

        self.assertNotIn("_test_gated", [m.name for m in semantic.available_metrics([])])
        self.assertNotIn("_test_gated", [m.name for m in semantic.available_metrics(["inventory"])])
        self.assertIn("_test_gated", [m.name for m in semantic.available_metrics(["manufacturing"])])

    def test_get_metric_returns_none_for_ungranted_package(self):
        semantic.register_metric(
            name="_test_get_gated",
            description="test",
            input_schema={"type": "object", "properties": {}},
            package="hr_payroll",
        )(lambda **kw: {"result": {"ok": True}, "citations": []})

        self.assertIsNone(semantic.get_metric("_test_get_gated", []))
        self.assertIsNotNone(semantic.get_metric("_test_get_gated", ["hr_payroll"]))

    def test_get_metric_returns_none_for_unknown_name(self):
        self.assertIsNone(semantic.get_metric("_test_does_not_exist", ["inventory"]))

    def test_real_core_metrics_are_registered_at_startup(self):
        # Sanity check that CoreConfig.ready() actually ran and imported
        # apps.core.ai_tools -- a regression test for the app-startup wiring
        # itself, not just the registry's own logic.
        names = [m.name for m in semantic.available_metrics([])]
        self.assertIn("cash_position", names)
        self.assertIn("overdue_ar_balance", names)
        self.assertIn("overdue_ap_balance", names)
