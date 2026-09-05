from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from core.utils.tests.factories import CategoryFactory, UserFactory


class DirectMetadataMigrationTests(TransactionTestCase):
    migrate_from = [("posts", "0033_merge_20260807_0000")]
    migrate_to = [("posts", "0034_direct_publication_metadata")]

    def test_preserves_existing_values_and_copies_legacy_fallbacks(self):
        category = CategoryFactory()
        user = UserFactory()
        executor = MigrationExecutor(connection)
        service_targets = [target for target in executor.loader.graph.leaf_nodes() if target[0] == "services"]
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(self.migrate_to))
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from + service_targets).apps
        OldPost = old_apps.get_model("posts", "Post")
        OldMetadata = old_apps.get_model("services", "MetaData")
        cases = [
            (
                "Existing H1",
                "Existing description",
                "Legacy title",
                "Legacy H1",
                "Legacy description",
                "Existing H1",
                "Existing description",
            ),
            (None, None, "Legacy title", "Legacy H1", "д" * 255, "Legacy title", "д" * 255),
            ("   ", "", "", "Legacy H1", "Legacy description", "Legacy H1", "Legacy description"),
        ]
        originals = []
        for index, (
            h1,
            description,
            legacy_title,
            legacy_h1,
            legacy_description,
            title,
            expected_description,
        ) in enumerate(cases):
            legacy = OldMetadata.objects.create(
                title=legacy_title,
                h1=legacy_h1,
                description=legacy_description,
                text="<p>Preserve legacy rich text</p>",
            )
            post = OldPost.objects.create(
                title="Canonical",
                slug=f"migration-{index}",
                text="Body",
                rubric_id=category.pk,
                publisher_id=user.pk,
                page_h1=h1,
                meta_description=description,
                meta=legacy,
                absolute_url=f"/saved-{index}/",
            )
            originals.append((post, title, expected_description))
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to + service_targets).apps
        NewPost = apps.get_model("posts", "Post")
        for original, title, description in originals:
            post = NewPost.objects.get(pk=original.pk)
            self.assertEqual((post.meta_title, post.meta_description), (title, description))
            for field in (
                "title",
                "text",
                "slug",
                "absolute_url",
                "publisher_id",
                "rubric_id",
                "publish_date",
                "update_date",
                "meta_id",
            ):
                self.assertEqual(getattr(post, field), getattr(original, field))
            self.assertEqual(post.meta.text, "<p>Preserve legacy rich text</p>")
