"""ChatView HTTP-level tests (REQ-CORE-AI-001/004/008). Mocks chat.answer()
directly -- the orchestration logic itself is covered by test_chat.py; this
file is about the view's own responsibilities: auth, tenant-scoping
`active_packages` into the call, response shape, and the audit-log write."""

from unittest.mock import patch

from django_tenants.test.cases import TenantTestCase
from rest_framework.test import APIClient

from apps.ai_core.models import PendingApproval
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
            "pending_action": None,
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

    def test_happy_path_surfaces_pending_action_when_present(self):
        self.client.force_authenticate(user=self.user)
        fake_result = {
            "configured": True,
            "reply": "I've prepared that, please confirm.",
            "citations": [],
            "tool_calls": [{"tool": "create_journal_entry", "input": {}}],
            "pending_action": {"id": 7, "description": "A draft entry will be created."},
        }
        with patch("apps.ai_core.views.chat.answer", return_value=fake_result):
            response = self.client.post(
                "/api/v1/ai/chat/", {"message": "book this"}, format="json", HTTP_HOST="tenant.test.com"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pending_action"], {"id": 7, "description": "A draft entry will be created."})

    def test_writes_an_audit_log_entry(self):
        self.client.force_authenticate(user=self.user)
        fake_result = {"configured": True, "reply": "Answer.", "citations": [], "tool_calls": [], "pending_action": None}
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
        fake_result = {
            "configured": False,
            "reply": "Not configured yet.",
            "citations": [],
            "tool_calls": [],
            "pending_action": None,
        }
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


class PendingApprovalViewSetTests(TenantTestCase):
    """REQ-CORE-AI-007: the approve/reject endpoints backing the AI panel's
    confirmation UI."""

    def setUp(self):
        self.requester = User.objects.create_user(username="asker", password="x")
        self.approver = User.objects.create_user(username="teammate", password="x")
        self.client = APIClient()
        from apps.ai_core import actions

        actions.register_action(
            name="_test_view_write_action",
            description="Pretend to change something.",
            input_schema={"type": "object", "properties": {}},
        )(lambda user, **kw: {"result": {"ok": True}})

    def _create_pending(self):
        return PendingApproval.objects.create(
            action_name="_test_view_write_action", action_input={}, summary="Would do a thing.", requested_by=self.requester
        )

    def test_requires_authentication(self):
        response = self.client.get("/api/v1/ai/pending-approvals/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 403)

    def test_list_returns_pending_approvals(self):
        self._create_pending()
        self.client.force_authenticate(user=self.approver)
        response = self.client.get("/api/v1/ai/pending-approvals/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"] if "results" in response.data else response.data), 1)

    def test_any_authenticated_user_can_approve_a_teammates_proposal(self):
        approval = self._create_pending()
        self.client.force_authenticate(user=self.approver)
        response = self.client.post(f"/api/v1/ai/pending-approvals/{approval.id}/approve/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, PendingApproval.EXECUTED)
        self.assertEqual(approval.resolved_by, self.approver)

    def test_reject_marks_rejected(self):
        approval = self._create_pending()
        self.client.force_authenticate(user=self.approver)
        response = self.client.post(f"/api/v1/ai/pending-approvals/{approval.id}/reject/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, PendingApproval.REJECTED)

    def test_approving_an_already_resolved_approval_returns_400(self):
        approval = self._create_pending()
        self.client.force_authenticate(user=self.approver)
        self.client.post(f"/api/v1/ai/pending-approvals/{approval.id}/reject/", HTTP_HOST="tenant.test.com")
        response = self.client.post(f"/api/v1/ai/pending-approvals/{approval.id}/approve/", HTTP_HOST="tenant.test.com")
        self.assertEqual(response.status_code, 400)

    def test_filter_by_status(self):
        pending = self._create_pending()
        resolved = self._create_pending()
        resolved.reject(self.approver)
        self.client.force_authenticate(user=self.approver)
        response = self.client.get(
            "/api/v1/ai/pending-approvals/?status=pending", HTTP_HOST="tenant.test.com"
        )
        rows = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], pending.id)
