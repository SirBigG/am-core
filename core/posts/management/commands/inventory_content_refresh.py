import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from django.core.management.base import BaseCommand, CommandError

from core.posts.content_refresh import ContentApiClient, ContentRefreshError, inventory_posts


class Command(BaseCommand):
    help = "Exports a read-only, checksummed post inventory for a content refresh campaign."

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-url",
            default=os.getenv("CONTENT_REFRESH_BASE_URL") or os.getenv("SITE_URL"),
            help="Content API base URL (CONTENT_REFRESH_BASE_URL, falling back to SITE_URL).",
        )
        parser.add_argument(
            "--token",
            default=os.getenv("AGROMEGA_CONTENT_API_TOKEN"),
            help="Staff API token (prefer AGROMEGA_CONTENT_API_TOKEN to avoid shell history).",
        )
        parser.add_argument("--rubric", type=int, default=955)
        parser.add_argument("--page-size", type=int, default=100)
        parser.add_argument("--timeout", type=int, default=30)
        parser.add_argument("--output-dir")

    def handle(self, *args, **options):
        if not options["base_url"]:
            raise CommandError("Provide --base-url, CONTENT_REFRESH_BASE_URL, or SITE_URL.")
        if not options["token"]:
            raise CommandError("Provide AGROMEGA_CONTENT_API_TOKEN (preferred) or --token.")
        if not 1 <= options["page_size"] <= 100:
            raise CommandError("--page-size must be between 1 and 100.")

        output_dir = options["output_dir"] or self.default_output_dir(options["rubric"])
        client = ContentApiClient(options["base_url"], options["token"], options["timeout"])
        try:
            summary = inventory_posts(client, options["rubric"], output_dir, options["page_size"])
        except (ContentRefreshError, requests.RequestException, ValueError) as exc:
            raise CommandError(f"Inventory failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Read-only inventory complete: {summary['post_count']} posts in {output_dir}. "
                "No posts were changed."
            )
        )

    @staticmethod
    def default_output_dir(rubric_id):
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return Path("content_refresh_runs") / f"rubric-{rubric_id}-{timestamp}"
