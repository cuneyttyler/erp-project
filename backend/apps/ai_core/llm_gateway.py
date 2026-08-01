"""
LLM provider gateway (technical.md §8.8). A thin wrapper around the
Anthropic Messages API so the rest of `ai_core` never imports the `anthropic`
package directly -- swapping/multi-routing providers later is a change to
this one module, not every call site.

Metering against the tenant's "AI Action credits" (`REQ-CORE-AI-011`,
`product.md` §7.2) is explicitly NOT implemented yet -- see docs/notes.md.
This gateway is where that would hook in (every call already passes through
one place), but the billing/credit-ledger model itself doesn't exist yet.
"""

from dataclasses import dataclass, field
from typing import Any

import anthropic
from django.conf import settings


class LLMNotConfiguredError(Exception):
    """Raised when no API key is configured. Callers must catch this and
    degrade gracefully (REQ-CORE-AI-009) rather than crash -- an unconfigured
    AI assistant is an expected, supported state (e.g. before Cüneyt has
    supplied a provider API key), not an error condition."""


@dataclass
class LLMResponse:
    stop_reason: str
    text_blocks: list[str]
    tool_use_blocks: list[dict[str, Any]]  # [{"id": str, "name": str, "input": dict}, ...]
    raw_content: list[Any] = field(default_factory=list)  # passed back verbatim as assistant turn content
    input_tokens: int = 0
    output_tokens: int = 0


def _client() -> anthropic.Anthropic:
    api_key = getattr(settings, "AI_LLM_API_KEY", "") or ""
    if not api_key:
        raise LLMNotConfiguredError("No LLM API key configured (AI_LLM_API_KEY / ANTHROPIC_API_KEY).")
    return anthropic.Anthropic(api_key=api_key)


def create_message(system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
    """One call to the model. Raises LLMNotConfiguredError if unconfigured;
    lets anthropic's own exceptions (auth failure, rate limit, timeout)
    propagate for the caller to translate into the degrade-gracefully
    response required by REQ-CORE-AI-009."""
    client = _client()
    model = getattr(settings, "AI_LLM_MODEL", "claude-sonnet-5")
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
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
        raw_content=[block.model_dump() for block in response.content],
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def is_configured() -> bool:
    return bool(getattr(settings, "AI_LLM_API_KEY", ""))
