from django.core.management.base import BaseCommand

from core.companies.models import Product, match_product_post


class Command(BaseCommand):
    help = "Auto-link active products without posts to matching catalog posts."

    def add_arguments(self, parser):
        parser.add_argument("--category", help="Limit products by category slug.")
        parser.add_argument("--limit", type=int, help="Maximum number of products to inspect.")
        parser.add_argument("--dry-run", action="store_true", help="Report matches without saving them.")

    def handle(self, *args, **options):
        queryset = (
            Product.objects.select_related("category")
            .filter(active=True, post__isnull=True)
            .exclude(name__isnull=True)
            .exclude(name="")
            .order_by("id")
        )
        if options["category"]:
            queryset = queryset.filter(category__slug=options["category"])
        if options["limit"]:
            queryset = queryset[: options["limit"]]

        inspected = 0
        linked = 0
        for product in queryset:
            inspected += 1
            post = match_product_post(product)
            if not post:
                continue
            linked += 1
            self.stdout.write(f"{product.id}: {product.name} -> {post.title}")
            if not options["dry_run"]:
                Product.objects.filter(pk=product.pk, post__isnull=True).update(post=post)

        action = "Would link" if options["dry_run"] else "Linked"
        self.stdout.write(f"{action} {linked} of {inspected} inspected products.")
