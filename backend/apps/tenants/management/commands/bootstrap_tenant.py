import os

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

from apps.tenants.models import Client, Domain

ALL_PACKAGES = ["purchasing", "inventory", "manufacturing", "sales_crm", "hr_payroll", "pos", "ecommerce", "bi_analytics"]


class Command(BaseCommand):
    help = (
        "Creates a tenant ready to sign in to: its schema, the hostname that "
        "routes to it, an admin user, a first company (entity) and that "
        "company's starter chart of accounts. Idempotent -- re-running it "
        "adds whatever is missing and changes nothing that exists (it never "
        "resets a password). The admin password is read from the "
        "BOOTSTRAP_ADMIN_PASSWORD environment variable, not an argument, so "
        "it doesn't end up in shell history or process listings."
    )

    def add_arguments(self, parser):
        parser.add_argument("--schema", required=True, help="Postgres schema name, e.g. 'main'.")
        parser.add_argument("--name", required=True, help="The organization's display name.")
        parser.add_argument("--domain", required=True, help="Hostname that should open this tenant.")
        parser.add_argument("--admin-username", default="admin")
        parser.add_argument("--packages", default="all", help="Comma-separated package keys, or 'all'.")

    def handle(self, *args, **options):
        packages = ALL_PACKAGES if options["packages"] == "all" else [p for p in options["packages"].split(",") if p]
        unknown = sorted(set(packages) - set(ALL_PACKAGES))
        if unknown:
            raise CommandError(f"Unknown packages: {', '.join(unknown)}")

        tenant, created = Client.objects.get_or_create(
            schema_name=options["schema"], defaults={"name": options["name"], "active_packages": packages}
        )
        self.stdout.write(f"Tenant '{tenant.schema_name}': {'created (schema migrated)' if created else 'already exists'}")

        domain, created = Domain.objects.get_or_create(domain=options["domain"], defaults={"tenant": tenant, "is_primary": not tenant.domains.exists()})
        if domain.tenant_id != tenant.id:
            raise CommandError(f"{options['domain']} already routes to another tenant.")
        self.stdout.write(f"Domain {domain.domain}: {'added' if created else 'already routed here'}")

        with schema_context(tenant.schema_name):
            # Imported here: these are tenant-schema models.
            from apps.core.management.commands.seed_chart_of_accounts import TEKDUZEN_SEED
            from apps.core.models import Account, Entity, User

            username = options["admin_username"]
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"Admin user '{username}': already exists (password left as it is)")
            else:
                password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")
                if not password:
                    raise CommandError("Set BOOTSTRAP_ADMIN_PASSWORD to create the admin user.")
                User.objects.create_superuser(username=username, password=password)
                self.stdout.write(f"Admin user '{username}': created")

            entity, created = Entity.objects.get_or_create(code="MAIN", defaults={"name": options["name"]})
            self.stdout.write(f"Company '{entity.code}': {'created' if created else 'already exists'}")

            # Accounts belong to a company (Account.entity), which the older
            # seed_chart_of_accounts command predates -- so seed them here,
            # into the company just ensured, from the same list.
            added = 0
            for code, name, account_type, _parent in TEKDUZEN_SEED:
                _, was_created = Account.objects.get_or_create(entity=entity, code=code, defaults={"name": name, "account_type": account_type})
                added += was_created
            self.stdout.write(f"Chart of accounts: {added} added, {len(TEKDUZEN_SEED) - added} already there")

        self.stdout.write(self.style.SUCCESS(f"Ready: sign in as '{options['admin_username']}' at {options['domain']}"))
