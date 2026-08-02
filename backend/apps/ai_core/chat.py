"""
The chat orchestration (technical.md §8.3/§8.4): a tool-calling loop over
the semantic-layer (read) and action (write) registries, kept as a plain
function (not folded into the view) so it's testable without spinning up an
HTTP request.

Read path: `User question -> LLM call picks a registered metric (tool-
calling) -> semantic layer executes a deterministic query -> LLM narrates
the result, citing sources`. Executed immediately -- metrics are read-only
by construction (technical.md §8.2).

Write path: when the model calls a registered *action* instead, nothing
executes yet. A `PendingApproval` row is created (a durable, human-readable
preview of what would happen) and the tool result tells the model that --
the model can narrate "I've prepared this, please confirm" but the actual
mutation only happens if/when the user approves it via the AI panel
(views.PendingApprovalViewSet.approve), never from inside this loop
(REQ-CORE-AI-007).

The LLM never sees raw SQL access and never free-composes a query or
mutation -- it can only call a registered, typed tool
(technical.md §8.1/§8.2).
"""

import json

from django.conf import settings

from . import actions, llm_gateway, metering, semantic
from .models import PendingApproval

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
3. Some tools *mutate* data (create a record, approve a request). Calling one of those never executes \
it immediately -- it only prepares a proposal the user must explicitly confirm in the panel. Always \
tell the user you've prepared the action and it's waiting for their confirmation; never claim it's \
already done.
4. Reply in {language}, matching the user's own language, using correct Turkish financial/business \
terminology when replying in Turkish (not literal machine translation).
5. Keep answers concise and concrete -- lead with the number/answer, then a short explanation if useful.
"""

_LANGUAGE_NAMES = {"tr": "Turkish", "en": "English"}


def _system_prompt(locale: str) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(language=_LANGUAGE_NAMES.get(locale, "English"))


def _tool_specs(active_packages: list[str]) -> list[dict]:
    specs = [
        {"name": m.name, "description": m.description, "input_schema": m.input_schema}
        for m in semantic.available_metrics(active_packages)
    ]
    specs += [
        {"name": a.name, "description": a.description, "input_schema": a.input_schema}
        for a in actions.available_actions(active_packages)
    ]
    return specs


def answer(user, active_packages: list[str], locale: str, history: list[dict], message: str) -> dict:
    """
    `history`: [{"role": "user"|"assistant", "content": str}, ...] -- prior
    turns from this conversation, as the frontend already tracks them
    (ai-panel/store.ts). Stateless server-side by design for this pass: no
    conversation is persisted server-side beyond the audit log (see
    docs/notes.md on what a durable conversation model would add later).

    Returns {"configured": bool, "reply": str, "citations": [...],
    "tool_calls": [...], "pending_action": {...} | None}. `tool_calls` is
    for the caller (views.ChatView) to write into the audit trail
    (REQ-CORE-AI-008) -- never returned to the browser as part of the chat
    UI payload. `pending_action`, when present, is what the frontend
    renders as the confirm/reject prompt (REQ-AI-XCUT-003) -- only the
    *first* action proposed in a turn is surfaced this way; a model
    proposing more than one write action in a single turn is an edge case
    not handled beyond "the rest still got created as PendingApproval rows,
    just not shown inline" (they're still visible via the pending-approvals
    list, only the chat bubble itself only highlights one).
    """
    locale = locale if locale in _LANGUAGE_NAMES else "en"

    if not llm_gateway.is_configured():
        return {
            "configured": False,
            "reply": _NOT_CONFIGURED[locale],
            "citations": [],
            "tool_calls": [],
            "pending_action": None,
        }

    tools = _tool_specs(active_packages)
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    messages.append({"role": "user", "content": message})
    system = _system_prompt(locale)
    model = getattr(settings, "AI_LLM_MODEL", "claude-sonnet-5")

    citations: list[dict] = []
    tool_calls: list[dict] = []
    pending_action = None

    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            response = llm_gateway.create_message(system=system, messages=messages, tools=tools)
        except llm_gateway.LLMNotConfiguredError:
            return {
                "configured": False,
                "reply": _NOT_CONFIGURED[locale],
                "citations": [],
                "tool_calls": tool_calls,
                "pending_action": pending_action,
            }
        except Exception:
            # Anthropic SDK errors (auth/rate-limit/timeout/etc.) -- REQ-CORE-AI-009:
            # degrade gracefully rather than surface a raw exception to the user.
            return {
                "configured": True,
                "reply": _DEGRADED[locale],
                "citations": citations,
                "tool_calls": tool_calls,
                "pending_action": pending_action,
            }

        metering.record_usage(user, model, response)

        if response.stop_reason != "tool_use":
            reply_text = "\n".join(t for t in response.text_blocks if t).strip()
            if not reply_text:
                reply_text = _DEGRADED[locale]
            return {
                "configured": True,
                "reply": reply_text,
                "citations": citations,
                "tool_calls": tool_calls,
                "pending_action": pending_action,
            }

        messages.append({"role": "assistant", "content": response.raw_content})
        tool_result_blocks = []
        for call in response.tool_use_blocks:
            call_input = call["input"] or {}
            metric = semantic.get_metric(call["name"], active_packages)
            if metric is not None:
                try:
                    outcome = metric.func(**call_input)
                    payload = outcome.get("result")
                    citations.extend(outcome.get("citations", []))
                except Exception as exc:
                    payload = {"error": str(exc)}
                tool_calls.append({"tool": call["name"], "input": call_input, "kind": "metric"})
            else:
                action = actions.get_action(call["name"], active_packages)
                if action is None:
                    payload = {"error": f"Tool '{call['name']}' is not available on this tenant's plan."}
                else:
                    preview_fn = action.preview or (lambda **kw: actions.default_preview(action, kw))
                    try:
                        summary = preview_fn(**call_input)
                    except Exception as exc:
                        summary = f"{action.description} (preview failed: {exc})"
                    approval = PendingApproval.objects.create(
                        action_name=action.name,
                        action_input=call_input,
                        summary=summary,
                        requested_by=user,
                    )
                    if pending_action is None:
                        pending_action = {"id": approval.id, "description": summary}
                    payload = {
                        "status": "pending_approval",
                        "approval_id": approval.id,
                        "summary": summary,
                    }
                tool_calls.append({"tool": call["name"], "input": call_input, "kind": "action"})
            tool_result_blocks.append(
                {"type": "tool_result", "tool_use_id": call["id"], "content": json.dumps(payload, default=str)}
            )
        messages.append({"role": "user", "content": tool_result_blocks})

    return {
        "configured": True,
        "reply": _DEGRADED[locale],
        "citations": citations,
        "tool_calls": tool_calls,
        "pending_action": pending_action,
    }
