"""Tests for the audit trail (what gets logged, who can read it) and for
reverting logged actions."""

import datetime
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from apps.access import audit, dispatch
from apps.access.models import UserGrant
from apps.access.permissions import forget
from apps.access.tests.base import HOST, SharedTenantTestCase
from apps.core.models import (
    Account,
    AuditLogEntry,
    Entity,
    Invoice,
    InvoiceLine,
    Item,
    JournalEntry,
    JournalLine,
    Party,
    Payment,
    User,
)
from apps.plugins.registry import PLUGINS


class AuditTestBase(SharedTenantTestCase):
    def setUp(self):
        self.tenant.active_packages = [p.package for p in PLUGINS if p.package]
        self.tenant.save()
        self.admin = User.objects.create_superuser(username="root", password="x")
        self.member = User.objects.create_user(username="member", password="x")
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def create_item(self, sku="A", name="Widget"):
        response = self.client.post("/api/v1/core/items/", {"sku": sku, "name": name}, format="json", **HOST)
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def entries(self, **filters):
        return list(AuditLogEntry.objects.filter(**filters).order_by("id"))

    def revert(self, entry):
        return self.client.post(f"/api/v1/access/audit-log/{entry.id}/revert/", **HOST)


class RecordingTests(AuditTestBase):
    def test_create_update_delete_are_each_logged_with_snapshots(self):
        item_id = self.create_item()
        self.client.patch(f"/api/v1/core/items/{item_id}/", {"name": "Gadget"}, format="json", **HOST)
        self.client.delete(f"/api/v1/core/items/{item_id}/", **HOST)

        created, updated, deleted = self.entries(target_type="item")
        self.assertEqual([e.action for e in (created, updated, deleted)], ["item.create", "item.update", "item.delete"])
        self.assertEqual({e.target_id for e in (created, updated, deleted)}, {str(item_id)})
        self.assertEqual((created.user, created.channel), (self.admin, audit.MANUAL))
        self.assertIsNone(created.before)
        self.assertEqual(created.after["name"], "Widget")
        self.assertEqual((updated.before["name"], updated.after["name"]), ("Widget", "Gadget"))
        self.assertEqual(deleted.before["name"], "Gadget")
        self.assertIsNone(deleted.after)
        self.assertIn("Gadget", deleted.target_label)

    def test_reads_and_failed_or_refused_writes_are_not_logged(self):
        self.client.get("/api/v1/core/items/", **HOST)
        self.client.post("/api/v1/core/items/", {"sku": ""}, format="json", **HOST)  # invalid
        self.client.force_authenticate(user=self.member)
        self.client.post("/api/v1/core/items/", {"sku": "A", "name": "A"}, format="json", **HOST)  # refused
        self.assertEqual(self.entries(), [])

    def test_state_transitions_are_logged_under_their_own_action(self):
        entity = Entity.objects.create(name="A", code="A")
        party = Party.objects.create(entity=entity, name="Acme")
        invoice = Invoice.objects.create(party=party, issue_date=timezone.localdate(), due_date=timezone.localdate())
        InvoiceLine.objects.create(invoice=invoice, description="x", quantity=1, unit_price=Decimal("100"))

        response = self.client.post(f"/api/v1/core/invoices/{invoice.id}/send_document/", **HOST)
        self.assertEqual(response.status_code, 200)
        (entry,) = self.entries()
        self.assertEqual(entry.action, "invoice.send_document")
        self.assertEqual((entry.before["status"], entry.after["status"]), ("draft", "sent"))

    def test_a_failed_transition_leaves_no_entry_and_no_partial_write(self):
        entity = Entity.objects.create(name="A", code="A")
        party = Party.objects.create(entity=entity, name="Acme")
        invoice = Invoice.objects.create(party=party, issue_date=timezone.localdate(), due_date=timezone.localdate())
        response = self.client.post(f"/api/v1/core/invoices/{invoice.id}/send_document/", **HOST)  # no lines
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.entries(), [])

    def test_channel_comes_from_the_server_never_the_client(self):
        self.client.post("/api/v1/core/items/", {"sku": "A", "name": "A"}, format="json", HTTP_X_ACTION_CHANNEL="ai", **HOST)
        self.assertEqual(self.entries()[0].channel, audit.MANUAL)

        result = dispatch.perform(self.admin, self.tenant, "item", "create", data={"sku": "B", "name": "B"}, channel=audit.AI)
        self.assertTrue(result.ok, result.data)
        self.assertEqual(self.entries()[-1].channel, audit.AI)
        self.assertEqual(self.entries()[-1].user, self.admin)

    def test_administration_changes_are_logged_without_the_password(self):
        response = self.client.post("/api/v1/access/users/", {"username": "ayse", "password": "a-Long-passphrase-9"}, format="json", **HOST)
        self.assertEqual(response.status_code, 201, response.data)
        (entry,) = self.entries(target_type="user")
        self.assertEqual(entry.action, "user.create")
        self.assertNotIn("password", entry.after)
        self.assertNotIn("a-Long-passphrase-9", str(entry.after))


class DispatchTests(AuditTestBase):
    def test_runs_as_the_user_with_their_permissions(self):
        result = dispatch.perform(self.member, self.tenant, "item", "create", data={"sku": "A", "name": "A"})
        self.assertEqual(result.status, 403)
        self.assertFalse(Item.objects.exists())

    def test_reads_and_validation_errors(self):
        self.create_item()
        listed = dispatch.perform(self.admin, self.tenant, "item", "view", params={"is_active": "true"})
        self.assertEqual(listed.data["count"], 1)
        one = dispatch.perform(self.admin, self.tenant, "item", "view", pk=listed.data["results"][0]["id"], handler="retrieve")
        self.assertEqual(one.data["sku"], "A")
        invalid = dispatch.perform(self.admin, self.tenant, "item", "create", data={"name": "no sku"})
        self.assertEqual(invalid.status, 400)
        self.assertIn("sku", invalid.error)

    def test_unknown_action_raises(self):
        with self.assertRaises(dispatch.UnknownAction):
            dispatch.perform(self.admin, self.tenant, "item", "launch")


class VisibilityTests(AuditTestBase):
    def setUp(self):
        super().setUp()
        self.create_item()
        self.client.post("/api/v1/core/entities/", {"name": "B", "code": "B"}, format="json", **HOST)

    def listed(self, as_user, **params):
        forget(as_user)  # the test reuses this object across requests
        self.client.force_authenticate(user=as_user)
        response = self.client.get("/api/v1/access/audit-log/", params, **HOST)
        self.assertEqual(response.status_code, 200)
        return response.data["results"]

    def test_admin_sees_everything(self):
        self.assertEqual({e["action"] for e in self.listed(self.admin)}, {"item.create", "entity.create"})

    def test_others_see_only_resources_they_can_view(self):
        # entity.view is open to everyone; item.view needs a grant.
        self.assertEqual([e["action"] for e in self.listed(self.member)], ["entity.create"])
        UserGrant.objects.create(user=self.member, actions=["item.view"])
        self.assertEqual({e["action"] for e in self.listed(self.member)}, {"item.create", "entity.create"})

    def test_everyone_sees_their_own_actions(self):
        UserGrant.objects.create(user=self.member, actions=["warehouse.create"])
        self.client.force_authenticate(user=self.member)
        self.client.post("/api/v1/inventory/warehouses/", {"code": "W", "name": "W"}, format="json", **HOST)
        self.assertIn("warehouse.create", [e["action"] for e in self.listed(self.member)])

    def test_filters(self):
        self.assertEqual([e["action"] for e in self.listed(self.admin, resource="item")], ["item.create"])
        self.assertEqual(self.listed(self.admin, channel="ai"), [])
        self.assertEqual(len(self.listed(self.admin, user=self.admin.id)), 2)
        self.assertEqual([e["action"] for e in self.listed(self.admin, q="Widget")], ["item.create"])
        tomorrow = str(timezone.localdate() + datetime.timedelta(days=1))
        self.assertEqual(self.listed(self.admin, date_from=tomorrow), [])

    def test_entry_reports_what_changed(self):
        item = Item.objects.get()
        self.client.force_authenticate(user=self.admin)
        self.client.patch(f"/api/v1/core/items/{item.id}/", {"name": "Gadget"}, format="json", **HOST)
        entry = self.listed(self.admin, action="item.update")[0]
        self.assertEqual(entry["changes"], [{"field": "name", "before": "Widget", "after": "Gadget"}])
        self.assertEqual(entry["user"]["username"], "root")


class RevertTests(AuditTestBase):
    def test_reverting_an_update_restores_the_previous_values(self):
        item_id = self.create_item()
        self.client.patch(f"/api/v1/core/items/{item_id}/", {"name": "Gadget", "unit_of_measure": "kg"}, format="json", **HOST)
        update = self.entries(action="item.update")[0]

        response = self.revert(update)
        self.assertEqual(response.status_code, 201, response.data)
        item = Item.objects.get(id=item_id)
        self.assertEqual((item.name, item.unit_of_measure), ("Widget", "adet"))
        # Logged as a new entry pointing back; the original is untouched.
        self.assertEqual(response.data["reverts"], update.id)
        self.assertEqual(response.data["action"], "item.update")
        self.assertEqual(AuditLogEntry.objects.get(id=update.id).after["name"], "Gadget")

    def test_reverting_a_create_deletes_and_a_delete_recreates(self):
        item_id = self.create_item()
        create = self.entries()[0]
        self.assertEqual(self.revert(create).status_code, 201)
        self.assertFalse(Item.objects.filter(id=item_id).exists())

        other_id = self.create_item(sku="B", name="Other")
        self.client.delete(f"/api/v1/core/items/{other_id}/", **HOST)
        delete = self.entries(action="item.delete", reverts__isnull=True)[0]
        self.assertEqual(self.revert(delete).status_code, 201)
        self.assertEqual(Item.objects.get(sku="B").name, "Other")

    def test_cannot_revert_twice_or_revert_a_revert(self):
        self.create_item()
        create = self.entries()[0]
        first = self.revert(create)
        self.assertEqual(self.revert(create).data["reason"], "already_reverted")
        self.assertEqual(self.revert(AuditLogEntry.objects.get(id=first.data["id"])).data["reason"], "is_a_revert")

    def test_only_the_latest_change_to_a_record_can_be_reverted(self):
        item_id = self.create_item()
        self.client.patch(f"/api/v1/core/items/{item_id}/", {"name": "Second"}, format="json", **HOST)
        self.client.patch(f"/api/v1/core/items/{item_id}/", {"name": "Third"}, format="json", **HOST)
        first, second = self.entries(action="item.update")

        self.assertEqual(self.revert(first).data["reason"], "changed_since")
        # Undo the later change, and the earlier one becomes revertible.
        self.assertEqual(self.revert(second).status_code, 201)
        self.assertEqual(self.revert(first).status_code, 201)
        self.assertEqual(Item.objects.get(id=item_id).name, "Widget")

    def test_reverting_needs_the_original_actions_permission(self):
        item_id = self.create_item()
        self.client.patch(f"/api/v1/core/items/{item_id}/", {"name": "Gadget"}, format="json", **HOST)
        update = self.entries(action="item.update")[0]
        UserGrant.objects.create(user=self.member, actions=["item.view"])
        self.client.force_authenticate(user=self.member)
        response = self.revert(update)
        self.assertEqual((response.status_code, response.data["reason"]), (400, "no_permission"))
        self.assertEqual(Item.objects.get(id=item_id).name, "Gadget")

    def test_entries_that_are_not_actions_or_have_no_inverse_are_not_revertible(self):
        chat = audit.record(user=self.admin, channel=audit.AI, action="ai_chat", target_type="conversation", target_id="1")
        self.assertEqual(self.revert(chat).data["reason"], "not_an_action")

        self.client.post("/api/v1/access/users/", {"username": "ayse", "password": "a-Long-passphrase-9"}, format="json", **HOST)
        user_created = self.entries(action="user.create")[0]
        # Users can't be deleted, so creating one has no inverse.
        self.assertEqual(self.revert(user_created).data["reason"], "not_reversible")

    def test_revert_status_is_reported_on_each_entry(self):
        self.create_item()
        response = self.client.get("/api/v1/access/audit-log/", **HOST)
        self.assertEqual(response.data["results"][0]["revert"], {"can_revert": True, "reason": None})


class CompensatingRevertTests(AuditTestBase):
    def setUp(self):
        super().setUp()
        self.entity = Entity.objects.create(name="A", code="A")
        self.party = Party.objects.create(entity=self.entity, name="Acme")
        today = timezone.localdate()
        self.invoice = Invoice.objects.create(party=self.party, issue_date=today, due_date=today)
        InvoiceLine.objects.create(invoice=self.invoice, description="x", quantity=1, unit_price=Decimal("100"))

    def test_sending_an_invoice_can_be_reverted_to_draft(self):
        self.client.post(f"/api/v1/core/invoices/{self.invoice.id}/send_document/", **HOST)
        sent = self.entries()[0]
        self.assertEqual(self.revert(sent).status_code, 201)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.DRAFT)
        undo = self.entries()[-1]
        self.assertEqual((undo.reverts, undo.before["status"], undo.after["status"]), (sent, "sent", "draft"))

    def test_reverting_a_payment_reopens_the_invoice(self):
        self.client.post(f"/api/v1/core/invoices/{self.invoice.id}/send_document/", **HOST)
        response = self.client.post(
            "/api/v1/core/payments/", {"invoice": self.invoice.id, "amount": "100.00", "date": str(timezone.localdate())}, format="json", **HOST
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.PAID)

        paid = self.entries(action="payment.create")[0]
        self.assertEqual(self.revert(paid).status_code, 201)
        self.assertFalse(Payment.objects.exists())
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.SENT)

    def test_reverting_a_posting_posts_a_reversing_entry(self):
        cash = Account.objects.create(entity=self.entity, code="100", name="Kasa", account_type=Account.ASSET)
        revenue = Account.objects.create(entity=self.entity, code="600", name="Satış", account_type=Account.REVENUE)
        entry = JournalEntry.objects.create(entity=self.entity, date=timezone.localdate(), memo="Sale")
        JournalLine.objects.create(journal_entry=entry, account=cash, debit=Decimal("250"))
        JournalLine.objects.create(journal_entry=entry, account=revenue, credit=Decimal("250"))
        self.client.post(f"/api/v1/core/journal-entries/{entry.id}/post_entry/", **HOST)
        posted = self.entries(action="journal_entry.post_entry")[0]

        self.assertEqual(self.revert(posted).status_code, 201)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.POSTED)  # history is never unposted
        reversal = JournalEntry.objects.exclude(id=entry.id).get()
        self.assertEqual(reversal.status, JournalEntry.POSTED)
        self.assertEqual(
            sorted((line.account.code, line.debit, line.credit) for line in reversal.lines.all()),
            [("100", Decimal("0"), Decimal("250")), ("600", Decimal("250"), Decimal("0"))],
        )

    def test_transitions_with_side_effects_elsewhere_are_not_revertible(self):
        from apps.access import catalog

        for code in ("purchase_order.receive", "sales_order.fulfill", "work_order.complete", "pos_shift.checkout", "payroll_run.finalize"):
            resource_key, operation = catalog.split_code(code)
            with self.subTest(action=code):
                self.assertIn(operation, catalog.get_resource(resource_key).operations)
                self.assertNotIn(operation, catalog.get_resource(resource_key).revert_handlers)
