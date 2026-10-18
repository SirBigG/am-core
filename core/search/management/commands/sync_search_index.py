import logging
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from core.search.indexing import sync_index

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Refresh dirty search resource scopes; --rebuild atomically replaces the entire index."

    def add_arguments(self, parser):
        parser.add_argument("--rebuild", action="store_true")
        parser.add_argument("--watch", action="store_true")
        parser.add_argument("--interval", type=float, default=2)
        parser.add_argument("--reconcile-seconds", type=float, default=300)

    def handle(self, *args, **options):
        if options["interval"] <= 0 or options["reconcile_seconds"] <= 0:
            raise CommandError("Intervals must be positive.")
        last_rebuild = time.monotonic()
        rebuild = options["rebuild"]
        while True:
            try:
                close_old_connections()
                reconcile = time.monotonic() - last_rebuild >= options["reconcile_seconds"]
                changed = sync_index(rebuild=rebuild or reconcile)
                if rebuild or reconcile:
                    last_rebuild = time.monotonic()
                rebuild = False
                if changed:
                    self.stdout.write(self.style.SUCCESS(f"Search index refreshed: {changed} resource scopes."))
            except KeyboardInterrupt:
                return
            except Exception:
                if not options["watch"]:
                    raise
                logger.exception("Search index refresh failed; queue retained for retry")
            if not options["watch"]:
                return
            try:
                time.sleep(options["interval"])
            except KeyboardInterrupt:
                return
