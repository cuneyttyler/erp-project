"""Registry behavior tests for the reporting-series registry (REQ-BI-001/002),
mirroring test_semantic.py/test_actions.py's shape exactly."""

from django.test import SimpleTestCase

from apps.ai_core import reporting


class SeriesRegistryTests(SimpleTestCase):
    def test_registered_series_with_no_package_is_always_available(self):
        reporting.register_series(
            name="_test_always_on_series", description="test", input_schema={"type": "object", "properties": {}}, chart_kind="time"
        )(lambda **kw: {"result": {"series": []}})

        self.assertIn("_test_always_on_series", [s.name for s in reporting.available_series([])])
        self.assertIn("_test_always_on_series", [s.name for s in reporting.available_series(["bi_analytics"])])

    def test_registered_series_with_package_requires_that_package(self):
        reporting.register_series(
            name="_test_gated_series",
            description="test",
            input_schema={"type": "object", "properties": {}},
            chart_kind="category",
            package="bi_analytics",
        )(lambda **kw: {"result": {"series": []}})

        self.assertNotIn("_test_gated_series", [s.name for s in reporting.available_series([])])
        self.assertIn("_test_gated_series", [s.name for s in reporting.available_series(["bi_analytics"])])

    def test_get_series_returns_none_for_ungranted_package(self):
        reporting.register_series(
            name="_test_get_gated_series",
            description="test",
            input_schema={"type": "object", "properties": {}},
            chart_kind="time",
            package="bi_analytics",
        )(lambda **kw: {"result": {"series": []}})

        self.assertIsNone(reporting.get_series("_test_get_gated_series", []))
        self.assertIsNotNone(reporting.get_series("_test_get_gated_series", ["bi_analytics"]))

    def test_get_series_returns_none_for_unknown_name(self):
        self.assertIsNone(reporting.get_series("_test_does_not_exist", ["bi_analytics"]))

    def test_real_core_series_are_registered_at_startup(self):
        names = [s.name for s in reporting.available_series([])]
        self.assertIn("monthly_revenue", names)
        self.assertIn("revenue_by_customer", names)
        self.assertIn("spend_by_vendor", names)
