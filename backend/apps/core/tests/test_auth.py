"""
Auth response shape tests. Regression coverage for a real bug: LoginView and
MeView used to build their response bodies independently, and only MeView
included `tenant.active_packages` -- the frontend's route/nav gating
(technical.md §10.1) reads that field straight off the login response, so a
tenant's packages silently vanished from the nav immediately after login
until the next /me/ poll. Both endpoints must return the identical shape.
"""

from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import User


class LoginTenantInfoTests(TenantTestCase):
    def setUp(self):
        User.objects.create_user(username="tester", password="secret123")
        self.tenant.active_packages = ["purchasing", "inventory"]
        self.tenant.save()
        self.client = APIClient()

    def test_login_response_includes_active_packages(self):
        response = self.client.post(
            "/api/v1/core/auth/login/",
            {"username": "tester", "password": "secret123"},
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data["tenant"]["active_packages"]), {"purchasing", "inventory"}
        )

    def test_me_response_matches_login_response_shape(self):
        login_response = self.client.post(
            "/api/v1/core/auth/login/",
            {"username": "tester", "password": "secret123"},
            format="json",
            HTTP_HOST="tenant.test.com",
        )
        me_response = self.client.get("/api/v1/core/auth/me/", HTTP_HOST="tenant.test.com")
        self.assertEqual(
            set(login_response.data["tenant"]["active_packages"]),
            set(me_response.data["tenant"]["active_packages"]),
        )
