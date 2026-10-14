"""Tests for the assistant: the catalog tools (tools.py), proposals and
their approval (models.PendingApproval), the conversation loop (chat.py)
and the HTTP endpoints.

The model itself is always mocked (`llm_gateway.create_message`) -- what's
under test is everything around it: that tools read and propose through
the user's own permissions, that nothing is changed until a person
approves, and that approved changes are validated, audited and attributed
correctly.
"""

import copy
from decimal import Decimal
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.access import audit
from apps.access.models import UserGrant
from apps.access.permissions import forget
from apps.access.tests.base import HOST, SharedTenantTestCase
from apps.ai_core import chat, tools
from apps.ai_core.llm_gateway import LLMNotConfiguredError, LLMResponse
from apps.ai_core.models import AIUsageRecord, Conversation, PendingApproval
from apps.core.models import (
    AuditLogEntry,
    Entity,
    Invoice,
    InvoiceLine,
    Item,
    Party,
    User,
)
from apps.plugins.registry import PLUGINS


def text_response(text):
    return LLMResponse(stop_reason="end_turn", text_blocks=[text], tool_use_blocks=[], raw_content=[{"type": "text", "text": text}], input_tokens=10, output_tokens=5)


def tool_response(*calls):
    """A model turn that calls tools: each call is (name, input)."""
    blocks = [{"id": f"call_{i}", "name": name, "input": tool_input} for i, (name, tool_input) in enumerate(calls)]
    return LLMResponse(
        stop_reason="tool_use",
        text_blocks=[],
        tool_use_blocks=blocks,
        raw_content=[{"type": "tool_use", **block} for block in blocks],
        input_tokens=10,
        output_tokens=5,
    )


class AssistantTestBase(SharedTenantTestCase):
    def setUp(self):
        self.tenant.active_packages = [p.package for p in PLUGINS if p.package]
        self.tenant.save()
        self.admin = User.objects.create_superuser(username="root", password="x")
        self.member = User.objects.create_user(username="member", password="x")
        self.ctx = tools.Context(user=self.admin, tenant=self.tenant)
        for sku, name, unit in [("A-1", "Anvil", "adet"), ("B-2", "Bolt", "kg"), ("C-3", "Cable", "kg")]:
            Item.objects.create(sku=sku, name=name, unit_of_measure=unit)

    def grant(self, *codes):
        UserGrant.objects.update_or_create(user=self.member, defaults={"actions": list(codes)})
        forget(self.member)
        return tools.Context(user=self.member, tenant=self.tenant)

    def invoices(self):
        entity = Entity.objects.create(name="A", code="A")
        today = timezone.localdate()
        for party_name, amount, month_offset in [("Acme", "100.00", 0), ("Acme", "250.00", 0), ("Globex", "900.00", 0)]:
            party, _ = Party.objects.get_or_create(entity=entity, name=party_name)
            invoice = Invoice.objects.create(party=party, issue_date=today, due_date=today, status=Invoice.SENT)
            InvoiceLine.objects.create(invoice=invoice, description="x", quantity=1, unit_price=Decimal(amount))


class CatalogToolTests(AssistantTestBase):
    def test_index_lists_only_what_the_user_may_do(self):
        index = tools.catalog_index(self.grant("item.view", "item.create"))
        self.assertIn("- item [view, create]", index)
        self.assertNotIn("invoice", index)
        # The administration area is never offered, even to an admin.
        self.assertNotIn("- user ", tools.catalog_index(self.ctx))
        self.assertIn("- invoice ", tools.catalog_index(self.ctx))

    def test_describe_resource_reports_fields_and_operation_inputs(self):
        payload, _ = tools.run(self.ctx, "describe_resource", {"resource": "purchase_order"})
        self.assertIn("id of party", payload["fields"]["party"]["type"])
        self.assertEqual(payload["fields"]["lines"]["type"], "list of objects")
        self.assertIn("lines", payload["operations"]["receive"]["data"])
        self.assertTrue(payload["operations"]["approve"]["needs_id"])

    def test_describe_resource_hides_operations_the_user_lacks(self):
        payload, _ = tools.run(self.grant("item.view"), "describe_resource", {"resource": "item"})
        self.assertEqual(list(payload["operations"]), ["view"])
        self.assertIn("error", tools.run(self.grant("item.view"), "describe_resource", {"resource": "invoice"})[0])

    def test_query_filters_sorts_limits_and_returns_a_table(self):
        payload, blocks = tools.run(
            self.ctx,
            "query_records",
            {"resource": "item", "where": [{"field": "unit_of_measure", "op": "eq", "value": "kg"}], "order_by": "-sku", "columns": ["sku", "name"], "title": "Kg items"},
        )
        self.assertEqual(payload["total_matching"], 2)
        self.assertEqual([row["sku"] for row in payload["rows"]], ["C-3", "B-2"])
        (table,) = blocks
        self.assertEqual((table["type"], table["title"], table["columns"], table["total"]), ("table", "Kg items", ["sku", "name"], 2))
        self.assertEqual(table["rows"][0], {"sku": "C-3", "name": "Cable"})

    def test_query_operators(self):
        def skus(where):
            return sorted(row["sku"] for row in tools.run(self.ctx, "query_records", {"resource": "item", "where": where})[0]["rows"])

        self.assertEqual(skus([{"field": "name", "op": "contains", "value": "BOL"}]), ["B-2"])
        self.assertEqual(skus([{"field": "sku", "op": "in", "value": ["A-1", "C-3"]}]), ["A-1", "C-3"])
        self.assertEqual(skus([{"field": "sku", "op": "gt", "value": "A-1"}]), ["B-2", "C-3"])
        self.assertEqual(skus([{"field": "unit_of_measure", "op": "ne", "value": "kg"}]), ["A-1"])

    def test_numbers_compare_as_numbers_not_text(self):
        self.invoices()
        payload, _ = tools.run(self.ctx, "query_records", {"resource": "invoice", "where": [{"field": "total", "op": "gt", "value": 200}], "order_by": "total"})
        # As text, "900.00" < "250.00" would be false and "1000" < "250".
        self.assertEqual([Decimal(row["total"]) for row in payload["rows"]], [Decimal("250"), Decimal("900")])

    def test_a_mistyped_field_is_an_error_not_an_empty_answer(self):
        payload, blocks = tools.run(self.ctx, "query_records", {"resource": "item", "where": [{"field": "colour", "op": "eq", "value": "red"}]})
        self.assertIn("no field 'colour'", payload["error"])
        self.assertIn("unit_of_measure", payload["error"])
        self.assertEqual(blocks, [])

    def test_reading_needs_the_view_permission(self):
        payload, blocks = tools.run(self.grant("item.create"), "query_records", {"resource": "item"})
        self.assertIn("does not have permission for item.view", payload["error"])
        self.assertEqual(blocks, [])

    def test_get_record_returns_the_full_record_as_a_card(self):
        item = Item.objects.get(sku="A-1")
        payload, (card,) = tools.run(self.ctx, "get_record", {"resource": "item", "id": item.id})
        self.assertEqual(payload["name"], "Anvil")
        self.assertEqual((card["type"], card["resource"], card["id"]), ("record", "item", str(item.id)))

    def test_summarize_counts_and_ranks_groups(self):
        payload, (chart,) = tools.run(self.ctx, "summarize_records", {"resource": "item", "group_by": "unit_of_measure"})
        self.assertEqual(payload["groups"], [{"group": "kg", "value": "2"}, {"group": "adet", "value": "1"}])
        self.assertEqual((chart["type"], chart["chart"], chart["format"]), ("chart", "hbar", "number"))

    def test_summarize_sums_a_measure_and_buckets_dates(self):
        self.invoices()
        payload, (chart,) = tools.run(
            self.ctx, "summarize_records", {"resource": "invoice", "group_by": "party_name", "aggregate": "sum", "measure": "total", "chart": "bar"}
        )
        self.assertEqual({g["group"]: Decimal(g["value"]) for g in payload["groups"]}, {"Globex": Decimal("900"), "Acme": Decimal("350")})
        self.assertEqual((chart["chart"], chart["format"]), ("bar", "money"))

        payload, (chart,) = tools.run(self.ctx, "summarize_records", {"resource": "invoice", "group_by": "issue_date", "bucket": "month", "aggregate": "sum", "measure": "total"})
        self.assertEqual(payload["groups"], [{"group": f"{timezone.localdate():%Y-%m}", "value": "1250.00"}])
        self.assertEqual((chart["chart"], chart["label_kind"]), ("line", "month"))

    def test_summarize_as_a_table(self):
        _, (table,) = tools.run(self.ctx, "summarize_records", {"resource": "item", "group_by": "unit_of_measure", "chart": "none"})
        self.assertEqual(table["type"], "table")

    def test_unknown_resource_or_arguments_come_back_as_errors(self):
        self.assertIn("no resource 'unicorn'", tools.run(self.ctx, "query_records", {"resource": "unicorn"})[0]["error"])
        self.assertIn("Bad arguments", tools.run(self.ctx, "query_records", {"resource": "item", "nonsense": 1})[0]["error"])
        self.assertIn("needs a numeric", tools.run(self.ctx, "summarize_records", {"resource": "item", "group_by": "sku", "aggregate": "sum"})[0]["error"])


class ProposalTests(AssistantTestBase):
    def propose(self, ctx=None, **arguments):
        return tools.run(ctx or self.ctx, "propose_action", arguments)

    def test_proposing_changes_nothing(self):
        payload, (block,) = self.propose(resource="item", operation="create", data={"sku": "N-9", "name": "New"}, reason="Asked for it")
        self.assertEqual(payload["status"], "awaiting_user_approval")
        self.assertFalse(Item.objects.filter(sku="N-9").exists())
        approval = PendingApproval.objects.get()
        self.assertEqual(block, {"type": "proposal", "approval_id": approval.id})
        self.assertEqual((approval.action_name, approval.status, approval.requested_by), ("item.create", PendingApproval.PENDING, self.admin))
        self.assertEqual(approval.preview["reason"], "Asked for it")
        self.assertEqual(AuditLogEntry.objects.count(), 0)

    def test_invalid_data_is_rejected_before_it_reaches_the_user(self):
        payload, blocks = self.propose(resource="item", operation="create", data={"name": "No SKU"})
        self.assertIn("would be rejected", payload["error"])
        self.assertIn("sku", payload["error"])
        self.assertEqual((blocks, PendingApproval.objects.count()), ([], 0))

    def test_a_field_the_action_does_not_take_is_refused_not_silently_dropped(self):
        payload, _ = self.propose(resource="item", operation="create", data={"sku": "N-9", "name": "New", "unit": "kg"})
        self.assertIn("does not take: unit", payload["error"])
        self.assertIn("unit_of_measure", payload["error"])
        # Read-only fields can't be set either.
        self.assertIn("does not take: id", self.propose(resource="item", operation="create", data={"id": 7, "sku": "N", "name": "N"})[0]["error"])
        # An operation that takes no data, and one with a declared body.
        item = Item.objects.get(sku="A-1")
        self.assertIn("takes no data", self.propose(resource="item", operation="delete", id=item.id, data={"force": True})[0]["error"])
        self.assertIn("does not take: qty", self.propose(resource="work_order", operation="complete", id=1, data={"qty": 1})[0]["error"])
        self.assertFalse(PendingApproval.objects.exists())

    def test_an_update_previews_exactly_what_changes(self):
        item = Item.objects.get(sku="A-1")
        self.propose(resource="item", operation="update", id=item.id, data={"name": "Anvil XL", "unit_of_measure": "adet"})
        approval = PendingApproval.objects.get()
        self.assertEqual(approval.preview["changes"], [{"field": "name", "before": "Anvil", "after": "Anvil XL"}])
        self.assertIn("Anvil", approval.preview["target_label"])
        self.assertEqual(approval.target_id, str(item.id))

    def test_an_update_that_changes_nothing_is_not_proposed(self):
        item = Item.objects.get(sku="A-1")
        payload, _ = self.propose(resource="item", operation="update", id=item.id, data={"name": "Anvil"})
        self.assertIn("Nothing would change", payload["error"])
        self.assertFalse(PendingApproval.objects.exists())

    def test_needs_the_permission_and_an_existing_record(self):
        payload, _ = self.propose(self.grant("item.view"), resource="item", operation="create", data={"sku": "N", "name": "N"})
        self.assertIn("does not have permission for item.create", payload["error"])
        self.assertIn("pass its `id`", self.propose(resource="item", operation="delete")[0]["error"])
        self.assertIn("No item with id 99999", self.propose(resource="item", operation="delete", id=99999)[0]["error"])
        self.assertIn("only reads data", self.propose(resource="item", operation="view")[0]["error"])
        self.assertFalse(PendingApproval.objects.exists())

    def test_approving_performs_the_action_as_the_approver_through_the_audited_path(self):
        self.propose(resource="item", operation="create", data={"sku": "N-9", "name": "New"})
        approval = PendingApproval.objects.get()
        approver = User.objects.create_superuser(username="approver", password="x")

        approval.approve(approver, self.tenant)
        self.assertEqual((approval.status, approval.resolved_by), (PendingApproval.EXECUTED, approver))
        item = Item.objects.get(sku="N-9")
        self.assertEqual(approval.result["id"], item.id)
        (entry,) = AuditLogEntry.objects.all()
        self.assertEqual((entry.action, entry.channel, entry.user, entry.target_id), ("item.create", audit.AI, approver, str(item.id)))

    def test_approving_an_update_changes_only_the_proposed_fields(self):
        item = Item.objects.get(sku="B-2")
        self.propose(resource="item", operation="update", id=item.id, data={"name": "Bolt M8"})
        PendingApproval.objects.get().approve(self.admin, self.tenant)
        item.refresh_from_db()
        self.assertEqual((item.name, item.sku, item.unit_of_measure), ("Bolt M8", "B-2", "kg"))

    def test_someone_without_the_permission_cannot_approve_and_it_stays_pending(self):
        self.propose(resource="item", operation="create", data={"sku": "N-9", "name": "New"})
        approval = PendingApproval.objects.get()
        with self.assertRaises(Exception) as raised:
            approval.approve(self.member, self.tenant)
        self.assertIn("permission", str(raised.exception))
        approval.refresh_from_db()
        self.assertEqual(approval.status, PendingApproval.PENDING)
        self.assertFalse(Item.objects.filter(sku="N-9").exists())

    def test_an_action_refused_by_a_business_rule_fails_and_changes_nothing(self):
        entity = Entity.objects.create(name="A", code="A")
        party = Party.objects.create(entity=entity, name="Acme")
        invoice = Invoice.objects.create(party=party, issue_date=timezone.localdate(), due_date=timezone.localdate())  # no lines
        self.propose(resource="invoice", operation="send_document", id=invoice.id)
        approval = PendingApproval.objects.get()

        approval.approve(self.admin, self.tenant)
        self.assertEqual(approval.status, PendingApproval.FAILED)
        self.assertIn("no lines", approval.error)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.DRAFT)
        self.assertEqual(AuditLogEntry.objects.count(), 0)

    def test_reject_and_no_second_decision(self):
        self.propose(resource="item", operation="create", data={"sku": "N-9", "name": "New"})
        approval = PendingApproval.objects.get()
        approval.reject(self.admin)
        self.assertEqual(approval.status, PendingApproval.REJECTED)
        with self.assertRaises(Exception):
            approval.approve(self.admin, self.tenant)
        self.assertFalse(Item.objects.filter(sku="N-9").exists())

    def test_the_outcome_is_noted_in_the_conversation(self):
        conversation = Conversation.objects.create(user=self.admin, title="t", llm_messages=[{"role": "user", "content": "hi"}])
        ctx = tools.Context(user=self.admin, tenant=self.tenant, conversation=conversation)
        self.propose(ctx, resource="item", operation="create", data={"sku": "N-9", "name": "New"})
        PendingApproval.objects.get().approve(self.admin, self.tenant)
        conversation.refresh_from_db()
        note = conversation.llm_messages[-1]
        self.assertEqual(note["role"], "user")
        self.assertIn("[System note", note["content"])
        self.assertIn("carried out", note["content"])


@override_settings(AI_LLM_API_KEY="test-key-not-real")
class ConversationLoopTests(AssistantTestBase):
    def ask(self, responses, user=None, conversation=None, message="q"):
        """Runs one turn against scripted model responses. `self.sent` holds
        the `messages` of each model call as they were *at that call* -- the
        loop keeps appending to the same list, so the mock's own record of
        its arguments would show the final state for every call."""
        self.sent = []
        scripted = iter(responses)

        def respond(**kwargs):
            self.sent.append(copy.deepcopy(kwargs["messages"]))
            response = next(scripted)
            if isinstance(response, Exception):
                raise response
            return response

        with patch("apps.ai_core.chat.llm_gateway.create_message", side_effect=respond) as mock:
            result = chat.answer(user=user or self.admin, tenant=self.tenant, locale="en", message=message, conversation=conversation)
        return result, mock

    def test_tool_results_are_returned_to_the_model_and_rendered_as_blocks(self):
        result, mock = self.ask([tool_response(("query_records", {"resource": "item", "order_by": "sku"})), text_response("There are 3 items.")])
        self.assertEqual(result["reply"], "There are 3 items.")
        self.assertEqual([b["type"] for b in result["blocks"]], ["table"])
        self.assertEqual(result["tool_calls"], [{"tool": "query_records", "input": {"resource": "item", "order_by": "sku"}, "kind": "catalog"}])
        # Second call carries the tool result back.
        tool_result = self.sent[1][-1]["content"][0]
        self.assertEqual((tool_result["type"], tool_result["tool_use_id"]), ("tool_result", "call_0"))
        self.assertIn('"total_matching": 3', tool_result["content"])
        self.assertEqual(AIUsageRecord.objects.count(), 2)

    def test_parallel_tool_calls_answer_in_one_message(self):
        _, mock = self.ask(
            [
                tool_response(("query_records", {"resource": "item"}), ("summarize_records", {"resource": "item", "group_by": "unit_of_measure"})),
                text_response("Done."),
            ]
        )
        self.assertEqual(len(self.sent[1][-1]["content"]), 2)

    def test_a_change_is_only_proposed(self):
        result, _ = self.ask([tool_response(("propose_action", {"resource": "item", "operation": "create", "data": {"sku": "N-9", "name": "New"}})), text_response("Ready for approval.")])
        self.assertEqual(result["blocks"], [{"type": "proposal", "approval_id": PendingApproval.objects.get().id}])
        self.assertFalse(Item.objects.filter(sku="N-9").exists())

    def test_the_prompt_and_tools_reflect_the_users_permissions(self):
        self.grant("item.view")
        _, mock = self.ask([text_response("ok")], user=self.member)
        kwargs = mock.call_args.kwargs
        self.assertIn("- item [view]", kwargs["system"])
        self.assertNotIn("invoice", kwargs["system"])
        offered = {spec["name"] for spec in kwargs["tools"]}
        self.assertIn("query_records", offered)
        # Verified figures need the view permission behind them.
        self.assertNotIn("cash_position", offered)
        _, mock = self.ask([text_response("ok")])
        self.assertIn("cash_position", {spec["name"] for spec in mock.call_args.kwargs["tools"]})

    def test_a_figure_the_user_may_not_see_cannot_be_called_by_name(self):
        self.grant("item.view")
        result, mock = self.ask([tool_response(("cash_position", {})), text_response("I can't see that.")], user=self.member)
        self.assertIn("no tool 'cash_position'", self.sent[1][-1]["content"][0]["content"])
        self.assertEqual(result["tool_calls"][0]["kind"], "unknown")

    def test_a_series_tool_produces_a_chart(self):
        result, _ = self.ask([tool_response(("monthly_revenue", {"months": 3})), text_response("Here it is.")])
        (chart,) = result["blocks"]
        self.assertEqual((chart["type"], chart["chart"], chart["series_name"], len(chart["series"][0]["points"])), ("chart", "line", "monthly_revenue", 3))
        self.assertEqual(result["citations"], [{"label": "Mizan / Trial Balance", "route": "/trial-balance"}])

    def test_conversation_is_stored_for_the_person_and_for_the_model(self):
        conversation = Conversation.objects.create(user=self.admin, title="t")
        self.ask([tool_response(("query_records", {"resource": "item"})), text_response("Three items.")], conversation=conversation, message="How many items?")
        conversation.refresh_from_db()
        self.assertEqual([(m.role, m.text) for m in conversation.messages.all()], [("user", "How many items?"), ("assistant", "Three items.")])
        self.assertEqual(conversation.messages.last().blocks[0]["type"], "table")
        self.assertEqual([m["role"] for m in conversation.llm_messages], ["user", "assistant", "user", "assistant"])

        # The next turn replays that transcript, tool calls included.
        _, mock = self.ask([text_response("The second is Bolt.")], conversation=conversation, message="Which is the second?")
        sent = self.sent[0]
        self.assertEqual(len(sent), 5)
        self.assertEqual(sent[1]["content"][0]["type"], "tool_use")
        self.assertEqual(sent[-1], {"role": "user", "content": "Which is the second?"})

    def test_a_provider_error_mid_turn_degrades_and_leaves_a_valid_transcript(self):
        conversation = Conversation.objects.create(user=self.admin, title="t")
        result, _ = self.ask([tool_response(("query_records", {"resource": "item"})), RuntimeError("rate limited")], conversation=conversation)
        self.assertTrue(result["configured"])
        self.assertIn("can't reliably", result["reply"])
        conversation.refresh_from_db()
        # No dangling tool call for the next turn to trip over.
        self.assertEqual([(m["role"], isinstance(m["content"], str)) for m in conversation.llm_messages], [("user", True), ("assistant", True)])

    def test_gives_up_after_the_iteration_limit(self):
        endless = [tool_response(("query_records", {"resource": "item"}))] * (chat.MAX_TOOL_ITERATIONS + 2)
        result, mock = self.ask(endless)
        self.assertEqual(mock.call_count, chat.MAX_TOOL_ITERATIONS)
        self.assertIn("can't reliably", result["reply"])

    def test_long_histories_are_trimmed_on_a_turn_boundary(self):
        history = []
        for i in range(chat.MAX_HISTORY_TURNS + 5):
            history += [
                {"role": "user", "content": f"q{i}"},
                {"role": "assistant", "content": [{"type": "tool_use", "id": f"c{i}", "name": "query_records", "input": {}}]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"c{i}", "content": "{}"}]},
                {"role": "assistant", "content": f"a{i}"},
            ]
        trimmed = chat._trimmed(history)
        self.assertEqual(trimmed[0], {"role": "user", "content": "q5"})
        self.assertEqual(len(trimmed), chat.MAX_HISTORY_TURNS * 4)

    def test_not_configured(self):
        with override_settings(AI_LLM_API_KEY=""):
            result, mock = self.ask([text_response("never")])
        mock.assert_not_called()
        self.assertFalse(result["configured"])
        result, _ = self.ask([LLMNotConfiguredError()])
        self.assertFalse(result["configured"])


@override_settings(AI_LLM_API_KEY="test-key-not-real")
class EndpointTests(AssistantTestBase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def chat(self, responses, **body):
        with patch("apps.ai_core.chat.llm_gateway.create_message", side_effect=responses):
            return self.client.post("/api/v1/ai/chat/", {"message": "Add item N-9", "locale": "en", **body}, format="json", **HOST)

    def propose(self):
        response = self.chat([tool_response(("propose_action", {"resource": "item", "operation": "create", "data": {"sku": "N-9", "name": "New"}})), text_response("Ready.")])
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def test_chat_starts_a_conversation_and_returns_live_proposals(self):
        response = self.propose()
        self.assertEqual(response.data["conversation"]["title"], "Add item N-9")
        (block,) = response.data["blocks"]
        self.assertEqual((block["type"], block["approval"]["status"], block["approval"]["can_approve"]), ("proposal", "pending", True))
        self.assertNotIn("tool_calls", response.data)

    def test_each_turn_is_recorded_in_the_audit_trail(self):
        self.propose()
        (entry,) = AuditLogEntry.objects.all()
        self.assertEqual((entry.action, entry.channel, entry.user), ("ai_chat", audit.AI, self.admin))
        self.assertEqual(entry.before, {"message": "Add item N-9"})
        self.assertEqual(entry.after["tool_calls"][0]["tool"], "propose_action")

    def test_approving_from_the_api_and_reopening_the_conversation(self):
        response = self.propose()
        approval_id = response.data["blocks"][0]["approval"]["id"]
        approved = self.client.post(f"/api/v1/ai/pending-approvals/{approval_id}/approve/", **HOST)
        self.assertEqual((approved.status_code, approved.data["status"]), (200, "executed"))
        self.assertTrue(Item.objects.filter(sku="N-9").exists())

        # Reopened later, the stored proposal shows how it turned out.
        reopened = self.client.get(f"/api/v1/ai/conversations/{response.data['conversation']['id']}/", **HOST)
        assistant_message = reopened.data["messages"][-1]
        self.assertEqual(assistant_message["blocks"][0]["approval"]["status"], "executed")
        self.assertFalse(assistant_message["blocks"][0]["approval"]["can_approve"])

    def test_continuing_a_conversation(self):
        first = self.chat([text_response("Hello.")])
        second = self.chat([text_response("Again.")], conversation_id=first.data["conversation"]["id"])
        self.assertEqual(second.data["conversation"]["id"], first.data["conversation"]["id"])
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(Conversation.objects.get().messages.count(), 4)

    def test_conversations_are_private_to_their_owner(self):
        conversation_id = self.chat([text_response("Hello.")]).data["conversation"]["id"]
        self.client.force_authenticate(user=self.member)
        self.assertEqual(self.client.get("/api/v1/ai/conversations/", **HOST).data, [])
        self.assertEqual(self.client.get(f"/api/v1/ai/conversations/{conversation_id}/", **HOST).status_code, 404)
        self.assertEqual(self.chat([text_response("x")], conversation_id=conversation_id).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/v1/ai/conversations/{conversation_id}/", **HOST).status_code, 404)

    def test_owner_can_delete_a_conversation(self):
        conversation_id = self.chat([text_response("Hello.")]).data["conversation"]["id"]
        self.assertEqual(self.client.delete(f"/api/v1/ai/conversations/{conversation_id}/", **HOST).status_code, 204)
        self.assertFalse(Conversation.objects.exists())

    def test_proposals_are_visible_to_those_who_could_carry_them_out(self):
        approval_id = self.propose().data["blocks"][0]["approval"]["id"]
        self.client.force_authenticate(user=self.member)
        self.assertEqual(self.client.get("/api/v1/ai/pending-approvals/", **HOST).data["results"], [])
        self.assertEqual(self.client.post(f"/api/v1/ai/pending-approvals/{approval_id}/approve/", **HOST).status_code, 404)

        self.grant("item.create")
        listed = self.client.get("/api/v1/ai/pending-approvals/", **HOST).data["results"]
        self.assertEqual([(p["id"], p["can_approve"]) for p in listed], [(approval_id, True)])
        self.assertEqual(self.client.post(f"/api/v1/ai/pending-approvals/{approval_id}/approve/", **HOST).data["status"], "executed")
        self.assertEqual(AuditLogEntry.objects.get(action="item.create").user, self.member)

    def test_unconfigured_assistant_answers_without_creating_a_conversation(self):
        with override_settings(AI_LLM_API_KEY=""):
            response = self.chat([text_response("never")])
        self.assertEqual((response.status_code, response.data["configured"], response.data["conversation"]), (200, False, None))
        self.assertFalse(Conversation.objects.exists())

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.post("/api/v1/ai/chat/", {"message": "hi"}, format="json", **HOST).status_code, 403)
