from django.core.management.base import BaseCommand

from core.registry.import_jobs import process_registry_import_jobs


class Command(BaseCommand):
    help = "Processes queued registry import jobs."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Maximum number of jobs to process.")
        parser.add_argument("--poll", action="store_true", help="Keep polling for new jobs.")
        parser.add_argument("--sleep", type=int, default=10, help="Seconds to sleep between polling attempts.")

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit is None and not options["poll"]:
            limit = 1
        process_registry_import_jobs(
            limit=limit,
            poll=options["poll"],
            sleep_seconds=options["sleep"],
            stdout=self.stdout,
            stderr=self.stderr,
            style=self.style,
        )
