"""SavedView tests (REQ-CORE-UX-003)."""

from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import SavedView, User


class SavedViewAPITests(TenantTestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="x")
        self.bob = User.objects.create_user(username="bob", password="x")
        self.client = APIClient()

    def test_create_forces_owner_to_requesting_user(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(
            "/api/v1/core/saved-views/",
            {
                "screen_key": "items",
                "name": "My Layout",
                "config": {"columns": ["sku", "name"]},
                "owner": self.bob.id,  # attempted spoof -- must be ignored
            },
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["owner"], self.alice.id)

    def test_personal_view_not_visible_to_other_users(self):
        SavedView.objects.create(
            screen_key="items", name="Alice Personal", owner=self.alice, is_shared=False, config={}
        )
        self.client.force_authenticate(user=self.bob)
        response = self.client.get(
            "/api/v1/core/saved-views/", {"screen_key": "items"}, HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"] if "results" in response.data else response.data), 0)

    def test_shared_view_is_visible_to_other_users(self):
        SavedView.objects.create(
            screen_key="items", name="Team Layout", owner=self.alice, is_shared=True, config={}
        )
        self.client.force_authenticate(user=self.bob)
        response = self.client.get(
            "/api/v1/core/saved-views/", {"screen_key": "items"}, HTTP_HOST="tenant.test.com"
        )
        rows = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Team Layout")

    def test_screen_key_scopes_the_list(self):
        SavedView.objects.create(screen_key="items", name="Items View", owner=self.alice, config={})
        SavedView.objects.create(screen_key="invoices", name="Invoices View", owner=self.alice, config={})
        self.client.force_authenticate(user=self.alice)
        response = self.client.get(
            "/api/v1/core/saved-views/", {"screen_key": "items"}, HTTP_HOST="tenant.test.com"
        )
        rows = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["screen_key"], "items")

    def test_owner_can_update_own_view(self):
        view = SavedView.objects.create(screen_key="items", name="Mine", owner=self.alice, config={"a": 1})
        self.client.force_authenticate(user=self.alice)
        response = self.client.patch(
            f"/api/v1/core/saved-views/{view.id}/",
            {"config": {"a": 2}},
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_non_owner_cannot_update_shared_view(self):
        view = SavedView.objects.create(
            screen_key="items", name="Shared", owner=self.alice, is_shared=True, config={}
        )
        self.client.force_authenticate(user=self.bob)
        response = self.client.patch(
            f"/api/v1/core/saved-views/{view.id}/",
            {"config": {"tampered": True}},
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 403)

    def test_non_owner_cannot_delete_shared_view(self):
        view = SavedView.objects.create(
            screen_key="items", name="Shared", owner=self.alice, is_shared=True, config={}
        )
        self.client.force_authenticate(user=self.bob)
        response = self.client.delete(f"/api/v1/core/saved-views/{view.id}/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(SavedView.objects.filter(id=view.id).exists())
