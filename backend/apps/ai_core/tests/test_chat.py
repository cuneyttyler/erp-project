"""Tests for the tool-calling orchestration (technical.md §8.3), mocking
llm_gateway so these never make a real network call -- no API key exists in
CI/dev by default (docs/notes.md), and the orchestration logic itself is
what's under test here, not Anthropic's API.

metering.record_usage is also mocked out in the SimpleTestCase classes below
-- it writes an AIUsageRecord row, which needs a real tenant schema
(SimpleTestCase forbids DB access entirely). The metering write itself is
covered separately by test_models.py's AIUsageRecordTests and by
ChatAnswerActionRoutingTests below, which uses TenantTestCase precisely
because it needs a real PendingApproval/AIUsageRecord row."""

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django_tenants.test.cases import TenantTestCase

from apps.ai_core import actions, chat, semantic
from apps.ai_core.llm_gateway import LLMNotConfiguredError, LLMResponse
from apps.ai_core.models import AIUsageRecord, PendingApproval
from apps.core.models import User

_DUMMY_USER = User(id=1, username="dummy")


def _register_echo_metric():
    semantic.register_metric(
        name="_test_echo_metric",
        description="Echoes back its input for test purposes.",
        input_schema={"type": "object", "properties": {"value": {"type": "string"}}},
    )(lambda value="", **kw: {"result": {"echo": value}, "citations": [{"label": "Test Citation", "route": "/test"}]})


class ChatAnswerNotConfiguredTests(SimpleTestCase):
    @override_settings(AI_LLM_API_KEY="")
    def test_returns_not_configured_reply_without_calling_llm(self):
        with patch("apps.ai_core.chat.llm_gateway.create_message") as mock_create:
            result = chat.answer(user=_DUMMY_USER, active_packages=[], locale="en", history=[], message="What's my cash position?")
        mock_create.assert_not_called()
        self.assertFalse(result["configured"])
        self.assertEqual(result["citations"], [])
        self.assertIsNone(result["pending_action"])

    @override_settings(AI_LLM_API_KEY="")
    def test_not_configured_reply_is_in_requested_locale(self):
        with patch("apps.ai_core.chat.llm_gateway.create_message"):
            result_tr = chat.answer(user=_DUMMY_USER, active_packages=[], locale="tr", history=[], message="Nakit durumum ne?")
        self.assertIn("yapılandırılmadı", result_tr["reply"])


@override_settings(AI_LLM_API_KEY="test-key-not-real")
class ChatAnswerToolLoopTests(SimpleTestCase):
    def setUp(self):
        _register_echo_metric()
        # metering.record_usage writes to the DB -- irrelevant to what these
        # orchestration tests check, and forbidden under SimpleTestCase.
        patcher = patch("apps.ai_core.chat.metering.record_usage")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_direct_text_reply_when_model_does_not_call_a_tool(self):
        text_response = LLMResponse(stop_reason="end_turn", text_blocks=["Merhaba, nasıl yardımcı olabilirim?"], tool_use_blocks=[])
        with patch("apps.ai_core.chat.llm_gateway.create_message", return_value=text_response):
            result = chat.answer(user=_DUMMY_USER, active_packages=[], locale="tr", history=[], message="Selam")
        self.assertTrue(result["configured"])
        self.assertEqual(result["reply"], "Merhaba, nasıl yardımcı olabilirim?")
        self.assertEqual(result["tool_calls"], [])
        self.assertIsNone(result["pending_action"])

    def test_executes_tool_then_returns_narrated_final_answer(self):
        tool_use_response = LLMResponse(
            stop_reason="tool_use",
            text_blocks=[],
            tool_use_blocks=[{"id": "call_1", "name": "_test_echo_metric", "input": {"value": "hello"}}],
            raw_content=[{"type": "tool_use", "id": "call_1", "name": "_test_echo_metric", "input": {"value": "hello"}}],
        )
        final_response = LLMResponse(stop_reason="end_turn", text_blocks=["The echoed value is hello."], tool_use_blocks=[])

        with patch("apps.ai_core.chat.llm_gateway.create_message", side_effect=[tool_use_response, final_response]):
            result = chat.answer(user=_DUMMY_USER, active_packages=[], locale="en", history=[], message="Echo hello please")

        self.assertEqual(result["reply"], "The echoed value is hello.")
        self.assertEqual(result["tool_calls"], [{"tool": "_test_echo_metric", "input": {"value": "hello"}, "kind": "metric"}])
        self.assertEqual(result["citations"], [{"label": "Test Citation", "route": "/test"}])
        self.assertIsNone(result["pending_action"])

    def test_tool_gated_by_missing_package_returns_error_to_model_not_a_crash(self):
        semantic.register_metric(
            name="_test_gated_metric",
            description="test",
            input_schema={"type": "object", "properties": {}},
            package="manufacturing",
        )(lambda **kw: {"result": {"should": "not run"}, "citations": []})

        tool_use_response = LLMResponse(
            stop_reason="tool_use",
            text_blocks=[],
            tool_use_blocks=[{"id": "call_1", "name": "_test_gated_metric", "input": {}}],
            raw_content=[{"type": "tool_use", "id": "call_1", "name": "_test_gated_metric", "input": {}}],
        )
        final_response = LLMResponse(stop_reason="end_turn", text_blocks=["I can't check that on your current plan."], tool_use_blocks=[])

        # active_packages deliberately excludes "manufacturing" -- the tool
        # spec sent to the model won't even include it, but this also proves
        # get_metric() blocks execution even if the model somehow names it.
        with patch("apps.ai_core.chat.llm_gateway.create_message", side_effect=[tool_use_response, final_response]):
            result = chat.answer(user=_DUMMY_USER, active_packages=[], locale="en", history=[], message="pending work orders?")

        self.assertEqual(result["reply"], "I can't check that on your current plan.")

    def test_llm_exception_degrades_gracefully_instead_of_raising(self):
        with patch("apps.ai_core.chat.llm_gateway.create_message", side_effect=RuntimeError("network blew up")):
            result = chat.answer(user=_DUMMY_USER, active_packages=[], locale="en", history=[], message="What's my cash position?")
        self.assertTrue(result["configured"])
        self.assertTrue(len(result["reply"]) > 0)

    def test_llm_not_configured_error_mid_loop_reports_unconfigured(self):
        with patch("apps.ai_core.chat.llm_gateway.create_message", side_effect=LLMNotConfiguredError()):
            result = chat.answer(user=_DUMMY_USER, active_packages=[], locale="en", history=[], message="hi")
        self.assertFalse(result["configured"])

    def test_exceeding_max_iterations_degrades_rather_than_looping_forever(self):
        tool_use_response = LLMResponse(
            stop_reason="tool_use",
            text_blocks=[],
            tool_use_blocks=[{"id": "call_1", "name": "_test_echo_metric", "input": {"value": "x"}}],
            raw_content=[{"type": "tool_use", "id": "call_1", "name": "_test_echo_metric", "input": {"value": "x"}}],
        )
        with patch("apps.ai_core.chat.llm_gateway.create_message", return_value=tool_use_response):
            result = chat.answer(user=_DUMMY_USER, active_packages=[], locale="en", history=[], message="loop forever")
        self.assertTrue(result["configured"])
        self.assertEqual(len(result["tool_calls"]), chat.MAX_TOOL_ITERATIONS)


@override_settings(AI_LLM_API_KEY="test-key-not-real")
class ChatAnswerActionRoutingTests(TenantTestCase):
    """Unlike the metric path, calling a registered *action* must never
    execute it inline -- it must create a durable PendingApproval row and
    surface it as `pending_action` instead (REQ-CORE-AI-007). Needs a real
    tenant schema (TenantTestCase), since this is exactly the DB write
    test_chat.py's other classes mock away."""

    def setUp(self):
        self.user = User.objects.create_user(username="asker", password="x")
        actions.register_action(
            name="_test_chat_write_action",
            description="Pretend to change something.",
            input_schema={"type": "object", "properties": {"thing": {"type": "string"}}},
            preview=lambda **kw: f"Would change {kw.get('thing')}.",
        )(lambda user, **kw: {"result": {"changed": kw.get("thing")}})

    def test_action_call_creates_pending_approval_instead_of_executing(self):
        tool_use_response = LLMResponse(
            stop_reason="tool_use",
            text_blocks=[],
            tool_use_blocks=[{"id": "call_1", "name": "_test_chat_write_action", "input": {"thing": "widget"}}],
            raw_content=[{"type": "tool_use", "id": "call_1", "name": "_test_chat_write_action", "input": {"thing": "widget"}}],
        )
        final_response = LLMResponse(stop_reason="end_turn", text_blocks=["I've prepared that, please confirm."], tool_use_blocks=[])

        with patch("apps.ai_core.chat.llm_gateway.create_message", side_effect=[tool_use_response, final_response]):
            result = chat.answer(user=self.user, active_packages=[], locale="en", history=[], message="change the widget")

        self.assertEqual(PendingApproval.objects.count(), 1)
        approval = PendingApproval.objects.get()
        self.assertEqual(approval.status, PendingApproval.PENDING)
        self.assertEqual(approval.action_name, "_test_chat_write_action")
        self.assertEqual(approval.action_input, {"thing": "widget"})
        self.assertEqual(approval.summary, "Would change widget.")
        self.assertEqual(approval.requested_by, self.user)

        self.assertIsNotNone(result["pending_action"])
        self.assertEqual(result["pending_action"]["id"], approval.id)
        self.assertEqual(result["pending_action"]["description"], "Would change widget.")

    def test_action_call_records_usage(self):
        tool_use_response = LLMResponse(
            stop_reason="tool_use",
            text_blocks=[],
            tool_use_blocks=[{"id": "call_1", "name": "_test_chat_write_action", "input": {"thing": "widget"}}],
            raw_content=[{"type": "tool_use", "id": "call_1", "name": "_test_chat_write_action", "input": {"thing": "widget"}}],
            input_tokens=10,
            output_tokens=5,
        )
        final_response = LLMResponse(stop_reason="end_turn", text_blocks=["Done."], tool_use_blocks=[], input_tokens=8, output_tokens=3)

        with patch("apps.ai_core.chat.llm_gateway.create_message", side_effect=[tool_use_response, final_response]):
            chat.answer(user=self.user, active_packages=[], locale="en", history=[], message="change the widget")

        self.assertEqual(AIUsageRecord.objects.count(), 2)
        self.assertEqual(sum(r.input_tokens for r in AIUsageRecord.objects.all()), 18)
