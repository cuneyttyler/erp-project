"""PendingApproval state-machine tests (REQ-CORE-AI-007/010) and
AIUsageRecord ledger tests (REQ-CORE-AI-011). TenantTestCase because both
models live in TENANT_APPS -- unlike test_chat.py/test_semantic.py/
test_actions.py, real DB writes (including the AuditLogEntry side effect)
are exactly what's under test here."""

from django_tenants.test.cases import TenantTestCase

from apps.ai_core import actions
from apps.ai_core.models import AIUsageRecord, PendingApproval
from apps.core.models import AuditLogEntry, User


def _register_test_actions():
    actions.register_action(
        name="_test_model_ok_action",
        description="Always succeeds.",
        input_schema={"type": "object", "properties": {}},
    )(lambda user, **kw: {"result": {"did": "it", "by": user.username}})

    actions.register_action(
        name="_test_model_failing_action",
        description="Always raises.",
        input_schema={"type": "object", "properties": {}},
    )(_raise)

    actions.register_action(
        name="_test_model_gated_action",
        description="Only available with a package.",
        input_schema={"type": "object", "properties": {}},
        package="manufacturing",
    )(lambda user, **kw: {"result": {}})


def _raise(user, **kw):
    raise ValueError("boom")


class PendingApprovalApproveTests(TenantTestCase):
    def setUp(self):
        _register_test_actions()
        self.requester = User.objects.create_user(username="asker", password="x")
        self.approver = User.objects.create_user(username="approver", password="x")

    def test_approve_executes_action_and_marks_executed(self):
        approval = PendingApproval.objects.create(
            action_name="_test_model_ok_action", action_input={}, summary="do it", requested_by=self.requester
        )
        approval.approve(self.approver, active_packages=[])
        self.assertEqual(approval.status, PendingApproval.EXECUTED)
        self.assertEqual(approval.result, {"did": "it", "by": "approver"})
        self.assertEqual(approval.resolved_by, self.approver)
        self.assertIsNotNone(approval.resolved_at)

    def test_approve_writes_an_audit_log_entry(self):
        approval = PendingApproval.objects.create(
            action_name="_test_model_ok_action", action_input={}, summary="do it", requested_by=self.requester
        )
        approval.approve(self.approver, active_packages=[])
        entry = AuditLogEntry.objects.get(action="ai_action__test_model_ok_action")
        self.assertEqual(entry.actor, f"ai:{self.requester.id}")
        self.assertEqual(entry.after["status"], PendingApproval.EXECUTED)

    def test_approve_when_action_raises_marks_failed_not_executed(self):
        approval = PendingApproval.objects.create(
            action_name="_test_model_failing_action", action_input={}, summary="fails", requested_by=self.requester
        )
        approval.approve(self.approver, active_packages=[])
        self.assertEqual(approval.status, PendingApproval.FAILED)
        self.assertIn("boom", approval.error)
        self.assertIsNone(approval.result)

    def test_approving_twice_raises_validation_error(self):
        approval = PendingApproval.objects.create(
            action_name="_test_model_ok_action", action_input={}, summary="do it", requested_by=self.requester
        )
        approval.approve(self.approver, active_packages=[])
        with self.assertRaises(Exception):
            approval.approve(self.approver, active_packages=[])
        self.assertEqual(approval.status, PendingApproval.EXECUTED)

    def test_approve_when_action_no_longer_on_plan_raises(self):
        approval = PendingApproval.objects.create(
            action_name="_test_model_gated_action", action_input={}, summary="gated", requested_by=self.requester
        )
        with self.assertRaises(Exception):
            approval.approve(self.approver, active_packages=[])
        approval.refresh_from_db()
        self.assertEqual(approval.status, PendingApproval.PENDING)


class PendingApprovalRejectTests(TenantTestCase):
    def setUp(self):
        _register_test_actions()
        self.requester = User.objects.create_user(username="asker2", password="x")
        self.approver = User.objects.create_user(username="approver2", password="x")

    def test_reject_marks_rejected_without_running_the_action(self):
        approval = PendingApproval.objects.create(
            action_name="_test_model_ok_action", action_input={}, summary="do it", requested_by=self.requester
        )
        approval.reject(self.approver)
        self.assertEqual(approval.status, PendingApproval.REJECTED)
        self.assertIsNone(approval.result)
        self.assertEqual(approval.resolved_by, self.approver)

    def test_rejecting_twice_raises_validation_error(self):
        approval = PendingApproval.objects.create(
            action_name="_test_model_ok_action", action_input={}, summary="do it", requested_by=self.requester
        )
        approval.reject(self.approver)
        with self.assertRaises(Exception):
            approval.reject(self.approver)

    def test_rejecting_an_already_executed_approval_raises(self):
        approval = PendingApproval.objects.create(
            action_name="_test_model_ok_action", action_input={}, summary="do it", requested_by=self.requester
        )
        approval.approve(self.approver, active_packages=[])
        with self.assertRaises(Exception):
            approval.reject(self.approver)


class AIUsageRecordTests(TenantTestCase):
    def test_creating_a_usage_record_stores_token_counts(self):
        user = User.objects.create_user(username="metered", password="x")
        record = AIUsageRecord.objects.create(user=user, model="claude-sonnet-5", input_tokens=120, output_tokens=45)
        self.assertEqual(record.input_tokens, 120)
        self.assertEqual(record.output_tokens, 45)
        self.assertEqual(AIUsageRecord.objects.count(), 1)
