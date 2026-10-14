"""Tests for the BI package (REQ-BI-001/003): permission scoping for
SavedReport/Dashboard (mirrors SavedViewViewSet's own test coverage), the
available-series catalog, and running a registered series through the API."""

from decimal import Decimal

from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.ai_core import reporting
from apps.bi.models import Dashboard, DashboardTile, SavedReport
from apps.core.models import User


def _register_test_series():
    reporting.register_series(
        name="_test_bi_series",
        description="test",
        input_schema={"type": "object", "properties": {}},
        chart_kind="category",
    )(lambda **kw: {"result": {"series": [{"label": "A", "value": "10.00"}]}})


class BITestBase(TenantTestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(username="owner", password="x")
        self.other = User.objects.create_superuser(username="other", password="x")
        self.client = APIClient()
        self.tenant.active_packages = ["bi_analytics"]
        self.tenant.save()
        _register_test_series()


class PackageGatingTests(BITestBase):
    def test_requires_authentication(self):
        response = self.client.get("/api/v1/bi/reports/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 403)

    def test_blocked_without_active_bi_package(self):
        self.tenant.active_packages = []
        self.tenant.save()
        self.client.force_authenticate(user=self.owner)
        response = self.client.get("/api/v1/bi/reports/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 403)


class AvailableSeriesViewTests(BITestBase):
    def test_lists_registered_series(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get("/api/v1/bi/series/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 200)
        names = [s["name"] for s in response.data]
        self.assertIn("_test_bi_series", names)
        self.assertIn("monthly_revenue", names)


class RunSeriesViewTests(BITestBase):
    def test_runs_a_registered_series(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            "/api/v1/bi/series/run/", {"series_name": "_test_bi_series", "params": {}}, format="json", HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["series"], [{"label": "A", "value": "10.00"}])

    def test_unknown_series_returns_400(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            "/api/v1/bi/series/run/", {"series_name": "_does_not_exist", "params": {}}, format="json", HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(response.status_code, 400)


class SavedReportPermissionScopingTests(BITestBase):
    def test_owner_sees_their_own_personal_report(self):
        SavedReport.objects.create(name="Mine", series_name="_test_bi_series", owner=self.owner, is_shared=False)
        self.client.force_authenticate(user=self.owner)
        response = self.client.get("/api/v1/bi/reports/", HTTP_HOST="tenant.test.com")
        rows = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(rows), 1)

    def test_other_user_does_not_see_a_personal_report(self):
        SavedReport.objects.create(name="Mine", series_name="_test_bi_series", owner=self.owner, is_shared=False)
        self.client.force_authenticate(user=self.other)
        response = self.client.get("/api/v1/bi/reports/", HTTP_HOST="tenant.test.com")
        rows = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(rows), 0)

    def test_other_user_sees_a_shared_report(self):
        SavedReport.objects.create(name="Shared", series_name="_test_bi_series", owner=self.owner, is_shared=True)
        self.client.force_authenticate(user=self.other)
        response = self.client.get("/api/v1/bi/reports/", HTTP_HOST="tenant.test.com")
        rows = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(rows), 1)

    def test_creating_a_report_sets_the_requesting_user_as_owner(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            "/api/v1/bi/reports/",
            {"name": "New", "series_name": "_test_bi_series", "chart_type": "bar", "params": {}},
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 201, response.data)
        report = SavedReport.objects.get(id=response.data["id"])
        self.assertEqual(report.owner, self.owner)


class DashboardTests(BITestBase):
    def setUp(self):
        super().setUp()
        self.report_a = SavedReport.objects.create(name="A", series_name="_test_bi_series", owner=self.owner, is_shared=True)
        self.report_b = SavedReport.objects.create(name="B", series_name="_test_bi_series", owner=self.owner, is_shared=True)

    def test_add_tile_appends_at_the_next_position(self):
        self.client.force_authenticate(user=self.owner)
        dashboard = Dashboard.objects.create(name="Dash", owner=self.owner)
        r1 = self.client.post(f"/api/v1/bi/dashboards/{dashboard.id}/add-tile/", {"report_id": self.report_a.id}, format="json", HTTP_HOST="tenant.test.com")
        r2 = self.client.post(f"/api/v1/bi/dashboards/{dashboard.id}/add-tile/", {"report_id": self.report_b.id}, format="json", HTTP_HOST="tenant.test.com")
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(r2.data["position"], r1.data["position"] + 1)

    def test_reorder_tiles_persists_new_positions(self):
        self.client.force_authenticate(user=self.owner)
        dashboard = Dashboard.objects.create(name="Dash", owner=self.owner)
        tile_a = DashboardTile.objects.create(dashboard=dashboard, report=self.report_a, position=0)
        tile_b = DashboardTile.objects.create(dashboard=dashboard, report=self.report_b, position=1)

        response = self.client.post(
            f"/api/v1/bi/dashboards/{dashboard.id}/reorder-tiles/",
            [{"tile_id": tile_a.id, "position": 5}, {"tile_id": tile_b.id, "position": 0}],
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 200, response.data)
        tile_a.refresh_from_db()
        tile_b.refresh_from_db()
        self.assertEqual(tile_a.position, 5)
        self.assertEqual(tile_b.position, 0)

    def test_remove_tile(self):
        self.client.force_authenticate(user=self.owner)
        dashboard = Dashboard.objects.create(name="Dash", owner=self.owner)
        tile = DashboardTile.objects.create(dashboard=dashboard, report=self.report_a, position=0)
        response = self.client.post(f"/api/v1/bi/dashboards/{dashboard.id}/remove-tile/", {"tile_id": tile.id}, format="json", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(dashboard.tiles.count(), 0)
