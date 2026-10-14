"""
The assistant's conversation loop (technical.md §8.3/§8.4): a tool-calling
loop kept as a plain function (not folded into the view) so it's testable
without an HTTP request.

The model can call three kinds of tool, and never anything else -- it has
no SQL, no free-form query, and no way to write (technical.md §8.1/§8.2):

- **Catalog tools** (tools.py): read any resource the user can view, group
  and total records in code, and *propose* any action in the catalog.
- **Metrics** (semantic.py): named, verified figures ("cash position")
  that mean the same here as on the home panel.
- **Series** (reporting.py): named chartable figures ("monthly revenue").

Reads run immediately, as the user. A write never runs from here: the model
can only *propose* it, which records a PendingApproval that a person
approves or rejects in the UI (REQ-CORE-AI-007).

Everything is scoped to the user asking: a tool they lack the permission for
is not in the list handed to the model at all, and the catalog tools check
again on every call.
"""

import json
from typing import Optional

from django.utils import timezone

from apps.access.permissions import allowed

from . import llm_gateway, metering, reporting, semantic, tools
from .models import Conversation, ConversationMessage

# A request can chain several lookups before it can answer or propose
# ("find the customer, find their open invoices, propose a payment each").
MAX_TOOL_ITERATIONS = 10
# How much of the model-side transcript is replayed on each turn.
MAX_HISTORY_TURNS = 12

_NOT_CONFIGURED = {
    "tr": "AI asistanı bu ortamda henüz yapılandırılmadı (LLM API anahtarı eksik). Lütfen yöneticinizle iletişime geçin.",
    "en": "The AI assistant isn't configured in this environment yet (missing LLM API key). Please contact your administrator.",
}

_DEGRADED = {
    "tr": "Şu anda bu isteği güvenilir şekilde yerine getiremiyorum. Lütfen daha sonra tekrar deneyin.",
    "en": "I can't reliably do that right now. Please try again shortly.",
}

_SYSTEM_PROMPT_TEMPLATE = """You are the assistant built into an ERP used by small and mid-sized Turkish companies. \
People use you instead of clicking through screens: to look things up, to see figures as tables and charts, \
and to get work done -- creating, editing and processing records -- by describing it in plain language.

You act for one signed-in user and can do exactly what they are permitted to do, nothing more.

## What exists

These are the resources this user can reach, each with the operations they hold on it:

{catalog}

Call `describe_resource` to see a resource's exact fields before you filter on a field you haven't seen, \
or before you propose creating or editing a record. Do not guess field names.

## Reading

- Any figure, count or record you state must come from a tool result in this conversation. Never estimate, \
recall or invent one. If no tool can produce it, say so plainly.
- State only what the tool result contains. Do not split a total into parts, attach a date, or add any \
detail the result does not give -- a breakdown you were not given is an invented one. If a breakdown would \
help, call a tool that produces it, or offer to.
- Prefer a named metric or series tool when one matches the question -- those are the company's official \
definitions of those figures.
- Otherwise use `query_records` to list, `get_record` for one record in full, and `summarize_records` to \
count or total by group. `summarize_records` computes the numbers and draws the chart; never do arithmetic \
over rows yourself and never type out a chart's data.
- Tables, charts and record cards produced by tools are shown to the user automatically, underneath your \
reply. So do not repeat their rows in text: give the answer in a sentence or two, call out what matters \
(the total, the outlier, what's overdue), and let the table carry the detail. Refer to it as "the table \
below" or "the chart below".
- Only `query_records`, `get_record`, `summarize_records`, `propose_action` and the series tools show \
anything. Metric tools (single figures such as balances and totals) show nothing: state their figures in \
your reply, and never mention a table or chart that no tool in this turn produced. If the user should see \
the rows, also call `query_records`.
- When asked for a chart or graph, use `summarize_records` or a series tool. When asked to "show" or "list", \
use `query_records`.

## Changing things

- Every change goes through `propose_action`. It does not perform the change: it checks it and puts an \
approval card in front of the user. The change happens only if they approve.
- So never say something has been done, created, sent or updated. Say what you have prepared and that it \
is waiting for their approval.
- Find the real record first (`query_records`) and use its id; never invent an id. If a request could match \
more than one record, or a required detail is missing and can't be found with a tool, ask one short \
question instead of guessing.
- If `propose_action` reports the data would be rejected, read the reason, fix it, and propose again. If it \
reports the user lacks permission, tell them; do not look for another route.
- Several changes means several `propose_action` calls, one per record, which the user approves one by one.
- A message starting with "[System note" tells you how an earlier proposal turned out. It was not typed by \
the user; take it into account and don't reply to it as if they had said it.

## How to answer

Use the correct accounting and business terms for the language you are replying in. Lead with the answer, \
keep it short, and write in plain sentences. Do not use Markdown tables, headings or lists; **bold** for a \
key figure or name is the only formatting the interface renders."""

_LANGUAGE_NAMES = {"tr": "Turkish", "en": "English"}


def _context_note(ctx: tools.Context, language: str) -> str:
    """The part of the prompt that changes between calls -- kept out of the
    cached system prompt (see llm_gateway.create_message)."""
    note = f"Today is {timezone.localdate():%A, %Y-%m-%d}. The signed-in user is {ctx.user.get_full_name() or ctx.user.username}."
    if ctx.entity_id:
        note += f" They are working in the company (entity) with id {ctx.entity_id}; finance records and reports are scoped to it."
    # Stated per turn, last, and as a fact about the interface rather than a
    # preference: left to "match the user", a model follows whichever
    # language the conversation started in.
    note += f" The interface is set to {language}: write this reply in {language}, whatever language earlier turns were in."
    return note


def _named_tools(ctx: tools.Context, active_packages: list[str]) -> dict:
    """Metrics and series this user may be offered, by name."""
    named = {}
    for kind, registry in (("metric", semantic.available_metrics(active_packages)), ("series", reporting.available_series(active_packages))):
        for entry in registry:
            if entry.requires is None or allowed(ctx.user, ctx.tenant, entry.requires):
                named[entry.name] = (kind, entry)
    return named


def _tool_specs(named: dict) -> list[dict]:
    specs = list(tools.TOOL_SPECS)
    specs += [{"name": entry.name, "description": entry.description, "input_schema": entry.input_schema} for _, entry in named.values()]
    return specs


def _series_block(series, payload: dict) -> dict:
    return {
        "type": "chart",
        "title": "",
        "series_name": series.name,
        "chart": "line" if series.chart_kind == "time" else "hbar",
        "format": "money",
        "label_kind": "month" if series.chart_kind == "time" else "text",
        "series": [{"name": series.name, "points": payload["series"]}],
    }


def _trimmed(llm_messages: list) -> list:
    """The last MAX_HISTORY_TURNS turns. A turn starts at a message the user
    typed (plain-string content) -- cutting anywhere else could separate a
    tool call from its result, which the API rejects."""
    starts = [i for i, message in enumerate(llm_messages) if message["role"] == "user" and isinstance(message["content"], str)]
    if len(starts) <= MAX_HISTORY_TURNS:
        return llm_messages
    return llm_messages[starts[-MAX_HISTORY_TURNS] :]


def _result(configured: bool, reply: str, blocks=None, citations=None, tool_calls=None) -> dict:
    return {"configured": configured, "reply": reply, "blocks": blocks or [], "citations": citations or [], "tool_calls": tool_calls or []}


def answer(
    user,
    tenant,
    locale: str,
    message: str,
    conversation: Optional[Conversation] = None,
    entity_id: Optional[int] = None,
) -> dict:
    """One turn, start to finish -- answer_steps() without the progress."""
    steps = answer_steps(user, tenant, locale, message, conversation, entity_id)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            return done.value


def _progress(call_name: str, call_input: dict, kind: str) -> dict:
    """What the assistant is doing right now, for the person waiting: which
    tool, and on what -- never the full input (it can hold a long `where`)."""
    event = {"step": "tool", "tool": call_name, "kind": kind}
    for key in ("resource", "operation", "metric", "series"):
        if isinstance(call_input.get(key), str):
            event[key] = call_input[key]
    return event


def answer_steps(
    user,
    tenant,
    locale: str,
    message: str,
    conversation: Optional[Conversation] = None,
    entity_id: Optional[int] = None,
):
    """
    One turn, as a generator: it yields a progress event before each model
    call ({"step": "thinking"}) and each tool call ({"step": "tool", ...}),
    and *returns* the result -- {"configured", "reply", "blocks",
    "citations", "tool_calls"}:

    - `blocks` are the structured results to render with the reply, in the
      order the tools produced them (see tools.py for the shapes).
    - `tool_calls` is for the caller to write into the audit trail
      (REQ-CORE-AI-008) -- never returned to the browser.

    When a `conversation` is given, the turn is appended to it (both the
    person-facing messages and the model-side transcript) and its earlier
    turns are replayed as context.
    """
    locale = locale if locale in _LANGUAGE_NAMES else "en"
    if not llm_gateway.is_configured():
        return _result(False, _NOT_CONFIGURED[locale])

    ctx = tools.Context(user=user, tenant=tenant, conversation=conversation, entity_id=entity_id)
    active_packages = (tenant.active_packages if tenant else None) or []
    named = _named_tools(ctx, active_packages)
    specs = _tool_specs(named)
    system = _SYSTEM_PROMPT_TEMPLATE.format(catalog=tools.catalog_index(ctx))
    context_note = _context_note(ctx, _LANGUAGE_NAMES[locale])
    model = llm_gateway.model_name()

    history = _trimmed(list(conversation.llm_messages)) if conversation else []
    messages = [*history, {"role": "user", "content": message}]
    new_from = len(history)  # everything from here on is this turn's

    blocks: list[dict] = []
    citations: list[dict] = []
    tool_calls: list[dict] = []
    reply = _DEGRADED[locale]
    configured = True

    for _ in range(MAX_TOOL_ITERATIONS):
        yield {"step": "thinking"}
        try:
            response = llm_gateway.create_message(system=system, messages=messages, tools=specs, context=context_note)
        except llm_gateway.LLMNotConfiguredError:
            configured, reply = False, _NOT_CONFIGURED[locale]
            break
        except Exception:
            # Provider errors (auth, rate limit, timeout...) -- REQ-CORE-AI-009:
            # degrade gracefully rather than surface a raw exception.
            break

        metering.record_usage(user, model, response)
        messages.append({"role": "assistant", "content": response.raw_content})

        if response.stop_reason != "tool_use":
            # end_turn, or a stop the loop can't continue from (max_tokens,
            # refusal): whatever text there is, is the reply.
            text = "\n".join(t for t in response.text_blocks if t).strip()
            if text:
                reply = text
            break

        tool_results = []
        for call in response.tool_use_blocks:
            call_input = call["input"] or {}
            yield _progress(call["name"], call_input, "catalog" if tools.is_tool(call["name"]) else named.get(call["name"], ("unknown",))[0])
            if tools.is_tool(call["name"]):
                payload, new_blocks = tools.run(ctx, call["name"], call_input)
                blocks.extend(new_blocks)
                kind = "catalog"
            elif call["name"] in named:
                kind, entry = named[call["name"]]
                try:
                    outcome = entry.func(**call_input)
                    payload = outcome.get("result")
                    citations.extend(outcome.get("citations", []))
                    if kind == "series":
                        blocks.append(_series_block(entry, payload))
                except Exception as exc:
                    payload = {"error": str(exc)}
            else:
                payload, kind = {"error": f"There is no tool '{call['name']}' available to this user."}, "unknown"
            tool_calls.append({"tool": call["name"], "input": call_input, "kind": kind})
            tool_results.append({"type": "tool_result", "tool_use_id": call["id"], "content": json.dumps(payload, default=str)})
        # All results of one assistant turn go back in one user message.
        messages.append({"role": "user", "content": tool_results})
    else:
        # Ran out of iterations mid-tool-use: the transcript ends on tool
        # results, which can't be continued from as-is -- drop this turn's
        # model-side trace rather than store a transcript the API rejects.
        messages = messages[: new_from + 1] + [{"role": "assistant", "content": reply}]

    # De-duplicate citations, keeping first-seen order.
    seen, unique_citations = set(), []
    for citation in citations:
        key = (citation.get("label"), citation.get("route"))
        if key not in seen:
            seen.add(key)
            unique_citations.append(citation)

    if conversation is not None and configured:
        turn = messages[new_from:]
        if turn[-1]["role"] != "assistant":
            # A provider error interrupted the turn; close it so the next
            # one starts from a valid transcript.
            turn = [turn[0], {"role": "assistant", "content": reply}]
        conversation.llm_messages = [*history, *turn]
        conversation.save(update_fields=["llm_messages", "updated_at"])
        ConversationMessage.objects.create(conversation=conversation, role=ConversationMessage.USER, text=message)
        ConversationMessage.objects.create(
            conversation=conversation, role=ConversationMessage.ASSISTANT, text=reply, blocks=blocks, citations=unique_citations
        )

    return _result(configured, reply, blocks, unique_citations, tool_calls)
