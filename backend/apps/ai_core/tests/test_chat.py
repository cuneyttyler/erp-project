"""Tests for the tool-calling orchestration (technical.md §8.3), mocking
llm_gateway so these never make a real network call -- no API key exists in
CI/dev by default (docs/notes.md), and the orchestration logic itself is
what's under test here, not Anthropic's API."""

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.ai_core import chat, semantic
from apps.ai_core.llm_gateway import LLMNotConfiguredError, LLMResponse


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
            result = chat.answer(active_packages=[], locale="en", history=[], message="What's my cash position?")
        mock_create.assert_not_called()
        self.assertFalse(result["configured"])
        self.assertEqual(result["citations"], [])

    @override_settings(AI_LLM_API_KEY="")
    def test_not_configured_reply_is_in_requested_locale(self):
        with patch("apps.ai_core.chat.llm_gateway.create_message"):
            result_tr = chat.answer(active_packages=[], locale="tr", history=[], message="Nakit durumum ne?")
        self.assertIn("yapılandırılmadı", result_tr["reply"])


@override_settings(AI_LLM_API_KEY="test-key-not-real")
class ChatAnswerToolLoopTests(SimpleTestCase):
    def setUp(self):
        _register_echo_metric()

    def test_direct_text_reply_when_model_does_not_call_a_tool(self):
        text_response = LLMResponse(stop_reason="end_turn", text_blocks=["Merhaba, nasıl yardımcı olabilirim?"], tool_use_blocks=[])
        with patch("apps.ai_core.chat.llm_gateway.create_message", return_value=text_response):
            result = chat.answer(active_packages=[], locale="tr", history=[], message="Selam")
        self.assertTrue(result["configured"])
        self.assertEqual(result["reply"], "Merhaba, nasıl yardımcı olabilirim?")
        self.assertEqual(result["tool_calls"], [])

    def test_executes_tool_then_returns_narrated_final_answer(self):
        tool_use_response = LLMResponse(
            stop_reason="tool_use",
            text_blocks=[],
            tool_use_blocks=[{"id": "call_1", "name": "_test_echo_metric", "input": {"value": "hello"}}],
            raw_content=[{"type": "tool_use", "id": "call_1", "name": "_test_echo_metric", "input": {"value": "hello"}}],
        )
        final_response = LLMResponse(stop_reason="end_turn", text_blocks=["The echoed value is hello."], tool_use_blocks=[])

        with patch("apps.ai_core.chat.llm_gateway.create_message", side_effect=[tool_use_response, final_response]):
            result = chat.answer(active_packages=[], locale="en", history=[], message="Echo hello please")

        self.assertEqual(result["reply"], "The echoed value is hello.")
        self.assertEqual(result["tool_calls"], [{"tool": "_test_echo_metric", "input": {"value": "hello"}}])
        self.assertEqual(result["citations"], [{"label": "Test Citation", "route": "/test"}])

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
            result = chat.answer(active_packages=[], locale="en", history=[], message="pending work orders?")

        self.assertEqual(result["reply"], "I can't check that on your current plan.")

    def test_llm_exception_degrades_gracefully_instead_of_raising(self):
        with patch("apps.ai_core.chat.llm_gateway.create_message", side_effect=RuntimeError("network blew up")):
            result = chat.answer(active_packages=[], locale="en", history=[], message="What's my cash position?")
        self.assertTrue(result["configured"])
        self.assertTrue(len(result["reply"]) > 0)

    def test_llm_not_configured_error_mid_loop_reports_unconfigured(self):
        with patch("apps.ai_core.chat.llm_gateway.create_message", side_effect=LLMNotConfiguredError()):
            result = chat.answer(active_packages=[], locale="en", history=[], message="hi")
        self.assertFalse(result["configured"])

    def test_exceeding_max_iterations_degrades_rather_than_looping_forever(self):
        tool_use_response = LLMResponse(
            stop_reason="tool_use",
            text_blocks=[],
            tool_use_blocks=[{"id": "call_1", "name": "_test_echo_metric", "input": {"value": "x"}}],
            raw_content=[{"type": "tool_use", "id": "call_1", "name": "_test_echo_metric", "input": {"value": "x"}}],
        )
        with patch("apps.ai_core.chat.llm_gateway.create_message", return_value=tool_use_response):
            result = chat.answer(active_packages=[], locale="en", history=[], message="loop forever")
        self.assertTrue(result["configured"])
        self.assertEqual(len(result["tool_calls"]), chat.MAX_TOOL_ITERATIONS)
