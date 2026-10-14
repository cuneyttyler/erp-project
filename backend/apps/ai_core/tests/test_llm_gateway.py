"""Tests for the LLM gateway's Mistral adapter: that the neutral transcript
the rest of ai_core speaks is translated into what Mistral's API accepts,
and Mistral's reply back into it. The HTTP call is mocked -- these never
reach the network."""

import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.ai_core import llm_gateway

TOOLS = [{"name": "query_records", "description": "List records.", "input_schema": {"type": "object", "properties": {"resource": {"type": "string"}}}}]


def http_response(message, finish_reason="stop", status=200, usage=None):
    response = Mock(status_code=status, text=json.dumps({"message": "error body"}))
    response.json.return_value = {
        "choices": [{"message": message, "finish_reason": finish_reason}],
        "usage": usage or {"prompt_tokens": 120, "completion_tokens": 30},
    }
    return response


@override_settings(AI_LLM_PROVIDER="mistral", AI_LLM_API_KEY="test-key-not-real", AI_LLM_MODEL="mistral-large-latest")
class MistralAdapterTests(SimpleTestCase):
    def call(self, messages, reply, tools=TOOLS, **reply_kwargs):
        with patch("apps.ai_core.llm_gateway.requests.post", return_value=http_response(reply, **reply_kwargs)) as post:
            result = llm_gateway.create_message(system="You are the assistant.", messages=messages, tools=tools, context="Today is Tuesday.")
        return result, post.call_args

    def test_request_shape(self):
        _, call = self.call([{"role": "user", "content": "List items"}], {"role": "assistant", "content": "Here."})
        self.assertEqual(call.args[0], "https://api.mistral.ai/v1/chat/completions")
        self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer test-key-not-real")
        body = call.kwargs["json"]
        self.assertEqual(body["model"], "mistral-large-latest")
        self.assertEqual(body["messages"][0], {"role": "system", "content": "You are the assistant.\n\nToday is Tuesday."})
        self.assertEqual(body["messages"][1], {"role": "user", "content": "List items"})
        self.assertEqual(body["tool_choice"], "auto")
        self.assertEqual(
            body["tools"],
            [{"type": "function", "function": {"name": "query_records", "description": "List records.", "parameters": TOOLS[0]["input_schema"]}}],
        )

    def test_a_text_reply(self):
        result, _ = self.call([{"role": "user", "content": "Hi"}], {"role": "assistant", "content": "Hello there."})
        self.assertEqual(result.stop_reason, "end_turn")
        self.assertEqual(result.text_blocks, ["Hello there."])
        self.assertEqual(result.tool_use_blocks, [])
        self.assertEqual(result.raw_content, [{"type": "text", "text": "Hello there."}])
        self.assertEqual((result.input_tokens, result.output_tokens), (120, 30))

    def test_a_tool_call_reply(self):
        reply = {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "aB3dE6gH9", "type": "function", "function": {"name": "query_records", "arguments": '{"resource": "item"}'}}],
        }
        result, _ = self.call([{"role": "user", "content": "List items"}], reply, finish_reason="tool_calls")
        self.assertEqual(result.stop_reason, "tool_use")
        self.assertEqual(result.tool_use_blocks, [{"id": "aB3dE6gH9", "name": "query_records", "input": {"resource": "item"}}])
        # Stored as the neutral transcript, ready to be sent back next call.
        self.assertEqual(result.raw_content, [{"type": "tool_use", "id": "aB3dE6gH9", "name": "query_records", "input": {"resource": "item"}}])

    def test_arguments_may_arrive_already_parsed_or_malformed(self):
        def arguments_of(arguments):
            reply = {"role": "assistant", "content": "", "tool_calls": [{"id": "aB3dE6gH9", "function": {"name": "query_records", "arguments": arguments}}]}
            return self.call([{"role": "user", "content": "x"}], reply)[0].tool_use_blocks[0]["input"]

        self.assertEqual(arguments_of({"resource": "item"}), {"resource": "item"})
        self.assertEqual(arguments_of(""), {})
        self.assertEqual(arguments_of('{"resource": '), {"_unparsed_arguments": '{"resource": '})

    def test_content_as_a_list_of_chunks(self):
        reply = {"role": "assistant", "content": [{"type": "text", "text": "Part one. "}, {"type": "text", "text": "Part two."}]}
        result, _ = self.call([{"role": "user", "content": "x"}], reply)
        self.assertEqual(result.text_blocks, ["Part one. Part two."])

    def test_a_full_tool_round_trip_is_translated(self):
        transcript = [
            {"role": "user", "content": "List items"},
            {"role": "assistant", "content": [{"type": "text", "text": "Looking."}, {"type": "tool_use", "id": "aB3dE6gH9", "name": "query_records", "input": {"resource": "item"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "aB3dE6gH9", "content": '{"total_matching": 3}'}]},
        ]
        _, call = self.call(transcript, {"role": "assistant", "content": "Three."})
        sent = call.kwargs["json"]["messages"][1:]
        self.assertEqual(sent[0], {"role": "user", "content": "List items"})
        self.assertEqual(
            sent[1],
            {
                "role": "assistant",
                "content": "Looking.",
                "tool_calls": [{"id": "aB3dE6gH9", "type": "function", "function": {"name": "query_records", "arguments": '{"resource": "item"}'}}],
            },
        )
        self.assertEqual(sent[2], {"role": "tool", "tool_call_id": "aB3dE6gH9", "name": "query_records", "content": '{"total_matching": 3}'})

    def test_parallel_tool_results_become_one_tool_message_each(self):
        transcript = [
            {"role": "user", "content": "x"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "aaaaaaaa1", "name": "query_records", "input": {}},
                    {"type": "tool_use", "id": "aaaaaaaa2", "name": "get_record", "input": {}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "aaaaaaaa1", "content": "{}"},
                    {"type": "tool_result", "tool_use_id": "aaaaaaaa2", "content": "{}"},
                ],
            },
        ]
        _, call = self.call(transcript, {"role": "assistant", "content": "ok"})
        tool_messages = [m for m in call.kwargs["json"]["messages"] if m["role"] == "tool"]
        self.assertEqual([(m["tool_call_id"], m["name"]) for m in tool_messages], [("aaaaaaaa1", "query_records"), ("aaaaaaaa2", "get_record")])

    def test_a_conversation_begun_under_another_provider_still_works(self):
        """Its tool-call ids aren't in Mistral's nine-character form, and it
        may hold block types Mistral has no equivalent for."""
        foreign_id = "toolu_01ABCdefGHIjklMNOpqrSTU"
        transcript = [
            {"role": "user", "content": "x"},
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "", "signature": "abc"},
                    {"type": "text", "text": "Looking.", "citations": None},
                    {"type": "tool_use", "id": foreign_id, "name": "query_records", "input": {"resource": "item"}, "caller": None},
                ],
            },
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": foreign_id, "content": "{}"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "Three."}]},
            {"role": "user", "content": "And now?"},
        ]
        _, call = self.call(transcript, {"role": "assistant", "content": "ok"})
        sent = call.kwargs["json"]["messages"]
        call_id = sent[2]["tool_calls"][0]["id"]
        self.assertRegex(call_id, r"^[a-zA-Z0-9]{9}$")
        self.assertEqual(sent[3]["tool_call_id"], call_id)  # the result still pairs with its call
        self.assertEqual(sent[2]["content"], "Looking.")
        self.assertEqual(set(sent[2]), {"role", "content", "tool_calls"})

    def test_consecutive_user_messages_are_merged(self):
        transcript = [
            {"role": "user", "content": "Add the item"},
            {"role": "assistant", "content": "Ready for approval."},
            {"role": "user", "content": "[System note, not typed by the user] Proposal #1 was approved."},
            {"role": "user", "content": "Did it go through?"},
        ]
        _, call = self.call(transcript, {"role": "assistant", "content": "Yes."})
        sent = call.kwargs["json"]["messages"]
        self.assertEqual([m["role"] for m in sent], ["system", "user", "assistant", "user"])
        self.assertIn("Proposal #1 was approved.", sent[3]["content"])
        self.assertTrue(sent[3]["content"].endswith("Did it go through?"))

    def test_no_tools_means_no_tool_fields(self):
        _, call = self.call([{"role": "user", "content": "x"}], {"role": "assistant", "content": "ok"}, tools=[])
        self.assertNotIn("tools", call.kwargs["json"])
        self.assertNotIn("tool_choice", call.kwargs["json"])

    def test_truncated_reply_reports_max_tokens(self):
        result, _ = self.call([{"role": "user", "content": "x"}], {"role": "assistant", "content": "Cut off"}, finish_reason="length")
        self.assertEqual(result.stop_reason, "max_tokens")

    def test_an_error_response_raises_a_provider_error(self):
        with patch("apps.ai_core.llm_gateway.requests.post", return_value=http_response({}, status=401)):
            with self.assertRaises(llm_gateway.LLMProviderError) as raised:
                llm_gateway.create_message(system="s", messages=[{"role": "user", "content": "x"}], tools=[])
        self.assertIn("401", str(raised.exception))


class ProviderSelectionTests(SimpleTestCase):
    @override_settings(AI_LLM_PROVIDER="mistral", AI_LLM_API_KEY="")
    def test_missing_key_is_not_configured(self):
        self.assertFalse(llm_gateway.is_configured())
        with patch("apps.ai_core.llm_gateway.requests.post") as post:
            with self.assertRaises(llm_gateway.LLMNotConfiguredError):
                llm_gateway.create_message(system="s", messages=[], tools=[])
        post.assert_not_called()

    def test_model_defaults_per_provider(self):
        with override_settings(AI_LLM_PROVIDER="mistral", AI_LLM_MODEL=""):
            self.assertEqual(llm_gateway.model_name(), "mistral-large-latest")
        with override_settings(AI_LLM_PROVIDER="anthropic", AI_LLM_MODEL=""):
            self.assertEqual(llm_gateway.model_name(), "claude-sonnet-5")
        with override_settings(AI_LLM_PROVIDER="mistral", AI_LLM_MODEL="mistral-small-latest"):
            self.assertEqual(llm_gateway.model_name(), "mistral-small-latest")

    @override_settings(AI_LLM_PROVIDER="anthropic", AI_LLM_API_KEY="test-key-not-real")
    def test_anthropic_is_still_selectable(self):
        with patch("apps.ai_core.llm_gateway._anthropic_message", return_value="anthropic-result") as anthropic_call, patch(
            "apps.ai_core.llm_gateway.requests.post"
        ) as post:
            self.assertEqual(llm_gateway.create_message(system="s", messages=[], tools=[]), "anthropic-result")
        anthropic_call.assert_called_once()
        post.assert_not_called()
