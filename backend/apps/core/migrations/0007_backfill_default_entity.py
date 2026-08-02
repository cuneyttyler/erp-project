from django.db import migrations


DEFAULT_ENTITY_CODE = "MAIN"
DEFAULT_ENTITY_NAME = "Ana Şirket"


def backfill_default_entity(apps, schema_editor):
    """
    REQ-CORE-ENT-001: every tenant existed as an implicit single entity
    before this migration. Rather than leaving existing Account/
    JournalEntry/Party rows with entity=NULL (which would make them
    invisible to any entity-scoped query/report going forward), give every
    pre-existing tenant schema exactly one real Entity and attach all of
    its existing GL/AR/AP data to it -- the tenant keeps working exactly as
    before, just now explicitly single-entity instead of implicitly so.
    """
    Entity = apps.get_model("core", "Entity")
    Account = apps.get_model("core", "Account")
    JournalEntry = apps.get_model("core", "JournalEntry")
    Party = apps.get_model("core", "Party")

    needs_backfill = (
        Account.objects.filter(entity__isnull=True).exists()
        or JournalEntry.objects.filter(entity__isnull=True).exists()
        or Party.objects.filter(entity__isnull=True).exists()
    )
    if not needs_backfill:
        return

    default_entity, _ = Entity.objects.get_or_create(
        code=DEFAULT_ENTITY_CODE, defaults={"name": DEFAULT_ENTITY_NAME}
    )
    Account.objects.filter(entity__isnull=True).update(entity=default_entity)
    JournalEntry.objects.filter(entity__isnull=True).update(entity=default_entity)
    Party.objects.filter(entity__isnull=True).update(entity=default_entity)


def noop_reverse(apps, schema_editor):
    # Deliberately not reversed -- collapsing entities back to NULL would
    # lose real (if implicit) information about which rows were assigned
    # where once more than one Entity exists. Reversing this migration
    # without reversing 0006 first isn't a meaningful operation anyway.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_entity_account_is_intercompany_alter_account_code_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_default_entity, noop_reverse),
    ]
