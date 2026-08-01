"""ChatView HTTP-level tests (REQ-CORE-AI-001/004/008). Mocks chat.answer()
directly -- the orchestration logic itself is covered by test_chat.py; this
file is about the view's own responsibilities: auth, tenant-scoping
`active_packages` into the call, response shape, and the audit-log write."""

from unittest.mock import patch

from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.core.models import AuditLogEntry, User


class ChatViewTests(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="asker", password="x")
        self.tenant.active_packages = ["purchasing", "inventory"]
        self.tenant.save()
        self.client = APIClient()

    def test_requires_authentication(self):
        response = self.client.post(
            "/api/v1/ai/chat/", {"message": "hi"}, format="json", HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(response.status_code, 403)

    def test_happy_path_returns_reply_and_citations(self):
        self.client.force_authenticate(user=self.user)
        fake_result = {
            "configured": True,
            "reply": "You have 2,500 TRY overdue from customers.",
            "citations": [{"label": "AR Aging", "route": "/aging"}],
            "tool_calls": [{"tool": "overdue_ar_balance", "input": {}}],
        }
        with patch("apps.ai_core.views.chat.answer", return_value=fake_result) as mock_answer:
            response = self.client.post(
                "/api/v1/ai/chat/",
                {"message": "How much are customers late on?", "locale": "en"},
                format="json",
                HTTP_HOST="tenant.test.com",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["reply"], fake_result["reply"])
        self.assertEqual(response.data["citations"], fake_result["citations"])
        self.assertTrue(response.data["configured"])

        # The view must pass the *tenant's real* active_packages through, not
        # anything client-supplied -- REQ-CORE-AI-004's "no privileged AI
        # service account" guarantee starts here.
        call_kwargs = mock_answer.call_args.kwargs
        self.assertEqual(set(call_kwargs["active_packages"]), {"purchasing", "inventory"})
        self.assertEqual(call_kwargs["message"], "How much are customers late on?")
        self.assertEqual(call_kwargs["locale"], "en")

    def test_writes_an_audit_log_entry(self):
        self.client.force_authenticate(user=self.user)
        fake_result = {"configured": True, "reply": "Answer.", "citations": [], "tool_calls": []}
        with patch("apps.ai_core.views.chat.answer", return_value=fake_result):
            self.client.post(
                "/api/v1/ai/chat/", {"message": "test question"}, format="json", HTTP_HOST="tenant.test.com"
            )
        entry = AuditLogEntry.objects.get(action="ai_chat")
        self.assertEqual(entry.actor, f"ai:{self.user.id}")
        self.assertEqual(entry.before["message"], "test question")
        self.assertEqual(entry.after["reply"], "Answer.")

    def test_not_configured_state_still_returns_200_with_configured_false(self):
        self.client.force_authenticate(user=self.user)
        fake_result = {"configured": False, "reply": "Not configured yet.", "citations": [], "tool_calls": []}
        with patch("apps.ai_core.views.chat.answer", return_value=fake_result):
            response = self.client.post(
                "/api/v1/ai/chat/", {"message": "hi"}, format="json", HTTP_HOST="tenant.test.com"
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["configured"])

    def test_rejects_empty_message(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/ai/chat/", {"message": ""}, format="json", HTTP_HOST="tenant.test.com"
        )
        self.assertEqual(response.status_code, 400)
