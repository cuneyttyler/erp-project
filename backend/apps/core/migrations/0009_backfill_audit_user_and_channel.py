from django.db import migrations


def backfill(apps, schema_editor):
    """Entries written before `user`/`channel` existed carry both only in
    `actor` ("user:<id>" / "ai:<id>") -- copy them across so older history
    filters and displays like everything written since."""
    AuditLogEntry = apps.get_model("core", "AuditLogEntry")
    User = apps.get_model("core", "User")
    user_ids = set(User.objects.values_list("id", flat=True))
    for entry in AuditLogEntry.objects.filter(user__isnull=True):
        kind, _, raw_id = entry.actor.partition(":")
        entry.channel = "ai" if kind == "ai" else "manual"
        if raw_id.isdigit() and int(raw_id) in user_ids:
            entry.user_id = int(raw_id)
        entry.save(update_fields=["channel", "user"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_remove_role_users_alter_auditlogentry_options_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
