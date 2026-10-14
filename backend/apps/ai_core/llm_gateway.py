"""
LLM provider gateway (technical.md §8.8): the one module that talks to a
model provider. Nothing else in `ai_core` imports a provider SDK or knows a
provider's wire format, so changing or adding a provider is a change here
and in settings -- not in the conversation loop, the tools or the tests.

Two providers are implemented, chosen by `settings.AI_LLM_PROVIDER`:

- **mistral** (the default): Mistral's chat-completions API, over HTTPS.
- **anthropic**: the Anthropic Messages API, through its SDK.

The rest of `ai_core` speaks one neutral transcript format, and each
provider adapter translates to and from it:

    {"role": "user", "content": "text"}
    {"role": "assistant", "content": [{"type": "text", "text": ...},
                                      {"type": "tool_use", "id": ..., "name": ..., "input": {...}}]}
    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": ..., "content": "json"}]}

(That format is the Anthropic Messages shape, which is why the Anthropic
adapter passes it straight through.) Conversations are stored in it
(Conversation.llm_messages), so a conversation started under one provider
continues under another.

Every call is recorded in the usage ledger by the caller (metering.py,
REQ-CORE-AI-011); turning that ledger into "AI Action credits" billing
(product.md §7.2) is not built yet -- see docs/notes.md.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings

MISTRAL = "mistral"
ANTHROPIC = "anthropic"

# Room for a reply that narrates a table or walks through a proposal. This
# endpoint returns one JSON response per turn rather than a stream.
MAX_TOKENS = 16000
REQUEST_TIMEOUT_SECONDS = 120

MISTRAL_CHAT_URL = "https://api.mistral.ai/v1/chat/completions"
# Mistral only accepts tool-call ids of exactly nine letters/digits.
_MISTRAL_ID = re.compile(r"^[a-zA-Z0-9]{9}$")


class LLMNotConfiguredError(Exception):
    """Raised when no API key is configured. Callers must catch this and
    degrade gracefully (REQ-CORE-AI-009) rather than crash -- an unconfigured
    AI assistant is an expected, supported state (e.g. before a provider API
    key has been supplied), not an error condition."""


class LLMProviderError(Exception):
    """The provider answered with an error (bad key, rate limit, a request it
    rejects). Callers treat it like any other provider failure and degrade."""


@dataclass
class LLMResponse:
    stop_reason: str  # "tool_use" when the model called tools, otherwise "end_turn"/"max_tokens"/...
    text_blocks: list[str]
    tool_use_blocks: list[dict[str, Any]]  # [{"id": str, "name": str, "input": dict}, ...]
    raw_content: list[Any] = field(default_factory=list)  # the assistant turn, in the neutral transcript format
    input_tokens: int = 0
    output_tokens: int = 0


def provider() -> str:
    return getattr(settings, "AI_LLM_PROVIDER", MISTRAL)


def model_name() -> str:
    return getattr(settings, "AI_LLM_MODEL", "") or ("mistral-large-latest" if provider() == MISTRAL else "claude-sonnet-5")


def is_configured() -> bool:
    return bool(getattr(settings, "AI_LLM_API_KEY", ""))


def _api_key() -> str:
    api_key = getattr(settings, "AI_LLM_API_KEY", "") or ""
    if not api_key:
        raise LLMNotConfiguredError(f"No API key configured for the '{provider()}' LLM provider.")
    return api_key


def create_message(system: str, messages: list[dict], tools: list[dict], context: str = "") -> LLMResponse:
    """One call to the model. Raises LLMNotConfiguredError if unconfigured;
    lets provider failures (auth, rate limit, timeout) propagate for the
    caller to translate into the degrade-gracefully response required by
    REQ-CORE-AI-009.

    `system` is the stable part of the prompt (rules, the user's catalog of
    resources); `context` is the part that changes between calls (today's
    date, the selected company). They're kept apart so a provider with
    prompt caching can cache the stable part. `tools` are
    {"name", "description", "input_schema"} with a JSON Schema.
    """
    api_key = _api_key()
    if provider() == ANTHROPIC:
        return _anthropic_message(api_key, system, messages, tools, context)
    return _mistral_message(api_key, system, messages, tools, context)


# ---------------------------------------------------------------------------
# Mistral
# ---------------------------------------------------------------------------
def _mistral_id(tool_use_id: str) -> str:
    """Ids Mistral issued are already valid. Anything else -- an id from a
    conversation begun under another provider -- is mapped to a stable
    nine-character stand-in, the same one wherever it appears, so a call
    and its result still pair up."""
    if _MISTRAL_ID.match(tool_use_id or ""):
        return tool_use_id
    return hashlib.sha256((tool_use_id or "").encode()).hexdigest()[:9]


def _to_mistral_messages(system: str, context: str, messages: list[dict]) -> list[dict]:
    converted: list[dict] = [{"role": "system", "content": f"{system}\n\n{context}".strip()}]
    tool_names: dict[str, str] = {}  # tool-call id -> tool name, for the results that follow

    for message in messages:
        content = message["content"]
        if message["role"] == "assistant":
            blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
            text = "\n".join(block.get("text", "") for block in blocks if block.get("type") == "text").strip()
            tool_calls = []
            for block in blocks:
                # Other block types (another provider's reasoning blocks)
                # have no equivalent here and are left out.
                if block.get("type") != "tool_use":
                    continue
                call_id = _mistral_id(block["id"])
                tool_names[call_id] = block["name"]
                tool_calls.append({"id": call_id, "type": "function", "function": {"name": block["name"], "arguments": json.dumps(block.get("input") or {})}})
            entry: dict = {"role": "assistant", "content": text}
            if tool_calls:
                entry["tool_calls"] = tool_calls
            converted.append(entry)
        elif isinstance(content, list):
            # Tool results: one "tool" message per result.
            for block in content:
                if block.get("type") != "tool_result":
                    continue
                call_id = _mistral_id(block["tool_use_id"])
                result = block.get("content")
                converted.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": tool_names.get(call_id, ""),
                        "content": result if isinstance(result, str) else json.dumps(result, default=str),
                    }
                )
        elif converted[-1]["role"] == "user":
            # Two user messages in a row (a system note about a proposal's
            # outcome, then what the user typed next) become one turn.
            converted[-1]["content"] += f"\n\n{content}"
        else:
            converted.append({"role": "user", "content": content})
    return converted


def _mistral_text(content) -> str:
    """Message content is a string, or a list of typed chunks on models
    that return more than plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(chunk.get("text", "") for chunk in content if isinstance(chunk, dict) and chunk.get("type") == "text")
    return ""


def _mistral_message(api_key: str, system: str, messages: list[dict], tools: list[dict], context: str) -> LLMResponse:
    body: dict = {
        "model": model_name(),
        "max_tokens": MAX_TOKENS,
        # Mistral's default sampling is loose enough to embellish a figure
        # (it once split a real cash total into an invented cash/bank
        # breakdown). An ERP assistant should say the same thing twice.
        "temperature": 0,
        "messages": _to_mistral_messages(system, context, messages),
    }
    if tools:
        body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in tools]
        body["tool_choice"] = "auto"

    response = requests.post(
        MISTRAL_CHAT_URL,
        json=body,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise LLMProviderError(f"Mistral API error {response.status_code}: {response.text[:500]}")
    data = response.json()
    choice = data["choices"][0]
    message = choice["message"]

    text = _mistral_text(message.get("content")).strip()
    tool_use_blocks = []
    for call in message.get("tool_calls") or []:
        arguments = call["function"].get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError:
                # Passed on as-is: the tool layer answers a malformed call
                # with an error the model can read and correct.
                arguments = {"_unparsed_arguments": arguments}
        tool_use_blocks.append({"id": call["id"], "name": call["function"]["name"], "input": arguments or {}})

    raw_content: list[dict] = [{"type": "text", "text": text}] if text else []
    raw_content += [{"type": "tool_use", **block} for block in tool_use_blocks]
    usage = data.get("usage") or {}
    return LLMResponse(
        stop_reason="tool_use" if tool_use_blocks else {"length": "max_tokens"}.get(choice.get("finish_reason"), "end_turn"),
        text_blocks=[text] if text else [],
        tool_use_blocks=tool_use_blocks,
        raw_content=raw_content,
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
    )


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------
def _anthropic_message(api_key: str, system: str, messages: list[dict], tools: list[dict], context: str) -> LLMResponse:
    # Imported here so a deployment on another provider doesn't need the SDK.
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    # The stable prompt carries a cache breakpoint -- which also covers
    # `tools`, since tools render before the system prompt. The changing
    # context goes after it, so it never invalidates the cached prefix.
    system_blocks: list[dict] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    if context:
        system_blocks.append({"type": "text", "text": context})
    response = client.messages.create(
        model=model_name(),
        max_tokens=MAX_TOKENS,
        system=system_blocks,
        messages=messages,
        tools=tools,
    )
    text_blocks = [block.text for block in response.content if block.type == "text"]
    tool_use_blocks = [
        {"id": block.id, "name": block.name, "input": block.input}
        for block in response.content
        if block.type == "tool_use"
    ]
    return LLMResponse(
        stop_reason=response.stop_reason,
        text_blocks=text_blocks,
        tool_use_blocks=tool_use_blocks,
        # Echoed back unchanged on the next call -- including any thinking
        # blocks, which must be returned exactly as received.
        raw_content=[block.model_dump() for block in response.content],
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
