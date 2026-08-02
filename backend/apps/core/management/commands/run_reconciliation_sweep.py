from django.core.management.base import BaseCommand

from apps.core.agents import run_ar_reconciliation_sweep


class Command(BaseCommand):
    help = (
        "Runs the AR reconciliation sweep agentic-workflow preview "
        "(development-plan.md §5) against the current tenant schema. "
        "Manual/cron trigger until a Celery beat schedule exists -- see "
        "apps/core/tasks.py and docs/notes.md."
    )

    def add_arguments(self, parser):
        parser.add_argument("--threshold-days", type=int, default=30)

    def handle(self, *args, **options):
        summary = run_ar_reconciliation_sweep(threshold_days=options["threshold_days"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Swept: {summary['flagged_count']} invoice(s) overdue >{options['threshold_days']}d, "
                f"total {summary['total_overdue']} TRY."
            )
        )
