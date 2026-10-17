from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from core.utils.tests.factories import UserFactory


class GuideHubMigrationTests(TransactionTestCase):
    migrate_from = [
        ("classifier", "0014_categoryaiprofile_recommendation_rules"),
        ("posts", "0034_direct_publication_metadata"),
    ]
    migrate_to = [
        ("classifier", "0015_guide_hub_foundation"),
        ("posts", "0035_guide_hub_foundation"),
    ]

    def test_upgrade_defaults_and_rollback_preserve_existing_content(self):
        user = UserFactory()
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        OldCategory = old_apps.get_model("classifier", "Category")
        OldPost = old_apps.get_model("posts", "Post")
        category = OldCategory.objects.create(
            slug="existing-category",
            value="Existing category",
            absolute_url="/existing-category/",
            lft=1,
            rght=2,
            tree_id=1,
            level=0,
        )
        post = OldPost.objects.create(
            title="Existing article",
            text="Original body",
            slug="existing-article",
            rubric_id=category.pk,
            publisher_id=user.pk,
            absolute_url="/saved/article-1.html",
            status=False,
        )
        original_category = OldCategory.objects.values().get(pk=category.pk)
        original_post = OldPost.objects.values().get(pk=post.pk)

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        Category = apps.get_model("classifier", "Category")
        Post = apps.get_model("posts", "Post")
        Section = apps.get_model("posts", "GuideSection")
        Placement = apps.get_model("posts", "GuideSectionArticle")
        migrated_category = Category.objects.values().get(pk=category.pk)
        self.assertEqual(migrated_category.pop("presentation_mode"), "catalog")
        self.assertEqual(migrated_category, original_category)
        self.assertEqual(Post.objects.values().get(pk=post.pk), original_post)
        self.assertFalse(Section.objects.exists())
        self.assertFalse(Placement.objects.exists())
        section = Section.objects.create(category_id=category.pk, title="Existing article references")
        Placement.objects.create(section=section, post_id=post.pk)

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        apps = executor.loader.project_state(self.migrate_from).apps
        self.assertEqual(
            apps.get_model("classifier", "Category").objects.values().get(pk=category.pk), original_category
        )
        self.assertEqual(apps.get_model("posts", "Post").objects.values().get(pk=post.pk), original_post)
