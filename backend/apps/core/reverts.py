"""Core's compensating actions for apps.access.revert -- the undo for
transitions that can't be undone by simply putting columns back."""

from django.utils import timezone

from apps.access import audit
from apps.access.revert import RevertError

from .models import JournalEntry, JournalLine


def reverse_posting(entry, user, tenant, channel):
    """Undo for `journal_entry.post_entry`.

    A posted entry is immutable (REQ-CORE-GL-008) -- it can't go back to
    draft, and this doesn't pretend otherwise. The accounting-correct undo
    is what an accountant would do by hand: post a second entry with every
    debit and credit swapped, dated today, so the two net to zero and both
    stay on the books.
    """
    from .serializers import JournalEntrySerializer

    original = JournalEntry.objects.prefetch_related("lines").filter(pk=entry.target_id).first()
    if original is None or original.status != JournalEntry.POSTED:
        raise RevertError("failed", "The journal entry is no longer posted.")

    reversal = JournalEntry.objects.create(
        entity=original.entity,
        date=timezone.localdate(),
        memo=f"Reversal of JE#{original.id} {original.memo}".strip()[:255],
        created_by=user,
    )
    JournalLine.objects.bulk_create(
        JournalLine(journal_entry=reversal, account=line.account, debit=line.credit, credit=line.debit, description=line.description)
        for line in original.lines.all()
    )
    reversal.post()

    snapshot = JournalEntrySerializer(original).data
    audit.record(
        user=user,
        channel=channel,
        action=entry.action,
        target_type=entry.target_type,
        target_id=original.id,
        target_label=str(original),
        before=snapshot,
        after={**snapshot, "reversed_by_entry": reversal.id},
        reverts=entry,
    )
