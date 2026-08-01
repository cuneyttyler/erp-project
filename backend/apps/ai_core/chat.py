"""
The read-path chat orchestration (technical.md §8.3): a tool-calling loop
over the semantic-layer registry, kept as a plain function (not folded into
the view) so it's testable without spinning up an HTTP request.

`User question -> LLM call picks a registered metric (tool-calling) ->
semantic layer executes a deterministic query -> LLM narrates the result,
citing sources`. The LLM never sees raw SQL access and never free-composes a
query -- it can only call one of the metrics apps.core/inventory/purchasing/
sales_crm/manufacturing/hr_payroll registered via their `ai_tools.py`
(technical.md §8.1/§8.2).

Explicitly out of scope for this pass (see docs/notes.md):
- The write/action path (REQ-CORE-AI-007/010, `PendingApproval` state
  machine, technical.md §8.4) -- this engine is read-only.
- Metered billing against AI Action credits (REQ-CORE-AI-011, §8.8).
- RAG over unstructured documents (§8.7).
"""

import json

from . import llm_gateway, semantic

MAX_TOOL_ITERATIONS = 4

_NOT_CONFIGURED = {
    "tr": "AI asistanı bu ortamda henüz yapılandırılmadı (LLM API anahtarı eksik). Lütfen yöneticinizle iletişime geçin.",
    "en": "The AI assistant isn't configured in this environment yet (missing LLM API key). Please contact your administrator.",
}

_DEGRADED = {
    "tr": "Şu anda bu soruyu güvenilir şekilde yanıtlayamıyorum. Lütfen daha sonra tekrar deneyin.",
    "en": "I can't reliably answer that right now. Please try again shortly.",
}

_SYSTEM_PROMPT_TEMPLATE = """You are the embedded AI assistant inside a Turkish SME ERP platform \
(Core General Ledger/AR/AP, plus whichever of Inventory, Purchasing, Sales & CRM, Manufacturing, \
and HR & Payroll this tenant has purchased).

Rules you must follow:
1. For any question involving a number, balance, count, or business record, you MUST call one of \
the provided tools to get the real figure. Never estimate, guess, or fabricate a financial or \
operational figure -- if no tool can answer the question, say plainly that you don't have a way to \
verify that yet, rather than presenting an unverifiable number.
2. You may explain what a field, workflow, or report means in plain language without calling a tool.
3. You cannot create, update, or delete any record yet -- that capability doesn't exist in this \
version. If asked to perform an action, say so clearly and suggest the user do it directly in the \
relevant screen.
4. Reply in {language}, matching the user's own language, using correct Turkish financial/business \
terminology when replying in Turkish (not literal machine translation).
5. Keep answers concise and concrete -- lead with the number/answer, then a short explanation if useful.
"""

_LANGUAGE_NAMES = {"tr": "Turkish", "en": "English"}


def _system_prompt(locale: str) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(language=_LANGUAGE_NAMES.get(locale, "English"))


def _tool_specs(active_packages: list[str]) -> list[dict]:
    return [
        {"name": m.name, "description": m.description, "input_schema": m.input_schema}
        for m in semantic.available_metrics(active_packages)
    ]


def answer(active_packages: list[str], locale: str, history: list[dict], message: str) -> dict:
    """
    `history`: [{"role": "user"|"assistant", "content": str}, ...] -- prior
    turns from this conversation, as the frontend already tracks them
    (ai-panel/store.ts). Stateless server-side by design for this pass: no
    conversation is persisted server-side beyond the audit log (see
    docs/notes.md on what a durable conversation model would add later).

    Returns {"configured": bool, "reply": str, "citations": [...], "tool_calls": [...]}.
    `tool_calls` is included for the caller (views.ChatView) to write into
    the audit trail (REQ-CORE-AI-008) -- never returned to the browser as
    part of the chat UI payload.
    """
    locale = locale if locale in _LANGUAGE_NAMES else "en"

    if not llm_gateway.is_configured():
        return {"configured": False, "reply": _NOT_CONFIGURED[locale], "citations": [], "tool_calls": []}

    tools = _tool_specs(active_packages)
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    messages.append({"role": "user", "content": message})
    system = _system_prompt(locale)

    citations: list[dict] = []
    tool_calls: list[dict] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            response = llm_gateway.create_message(system=system, messages=messages, tools=tools)
        except llm_gateway.LLMNotConfiguredError:
            return {"configured": False, "reply": _NOT_CONFIGURED[locale], "citations": [], "tool_calls": tool_calls}
        except Exception:
            # Anthropic SDK errors (auth/rate-limit/timeout/etc.) -- REQ-CORE-AI-009:
            # degrade gracefully rather than surface a raw exception to the user.
            return {"configured": True, "reply": _DEGRADED[locale], "citations": citations, "tool_calls": tool_calls}

        if response.stop_reason != "tool_use":
            reply_text = "\n".join(t for t in response.text_blocks if t).strip()
            if not reply_text:
                reply_text = _DEGRADED[locale]
            return {"configured": True, "reply": reply_text, "citations": citations, "tool_calls": tool_calls}

        messages.append({"role": "assistant", "content": response.raw_content})
        tool_result_blocks = []
        for call in response.tool_use_blocks:
            metric = semantic.get_metric(call["name"], active_packages)
            if metric is None:
                payload = {"error": f"Tool '{call['name']}' is not available on this tenant's plan."}
            else:
                try:
                    outcome = metric.func(**(call["input"] or {}))
                    payload = outcome.get("result")
                    citations.extend(outcome.get("citations", []))
                except Exception as exc:
                    payload = {"error": str(exc)}
            tool_calls.append({"tool": call["name"], "input": call["input"]})
            tool_result_blocks.append(
                {"type": "tool_result", "tool_use_id": call["id"], "content": json.dumps(payload, default=str)}
            )
        messages.append({"role": "user", "content": tool_result_blocks})

    return {"configured": True, "reply": _DEGRADED[locale], "citations": citations, "tool_calls": tool_calls}
