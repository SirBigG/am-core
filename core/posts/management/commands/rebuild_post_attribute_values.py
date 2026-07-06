from django.core.management.base import BaseCommand

from core.posts.category_attributes import rebuild_post_attribute_values
from core.posts.models import Post


class Command(BaseCommand):
    help = "Rebuild the public category attribute filter index for posts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--category",
            dest="category_slug",
            help="Limit rebuilds to posts in the category with this slug.",
        )
        parser.add_argument(
            "--active-only",
            action="store_true",
            help="Only rebuild active posts.",
        )

    def handle(self, *args, **options):
        queryset = Post.objects.select_related("rubric").order_by("pk")
        if options["category_slug"]:
            queryset = queryset.filter(rubric__slug=options["category_slug"])
        if options["active_only"]:
            queryset = queryset.active()

        rebuilt_count = 0
        for post in queryset.iterator():
            rebuild_post_attribute_values(post)
            rebuilt_count += 1

        self.stdout.write(self.style.SUCCESS(f"Rebuilt attribute values for {rebuilt_count} posts."))
