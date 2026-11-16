from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from core.classifier.models import CategoryHub, CategoryHubSection
from core.utils.tests.factories import CategoryFactory


class SectionedHubMigrationTests(TransactionTestCase):
    def test_preserves_existing_potato_layout_without_rewriting_sources(self):
        root = CategoryFactory()
        potato = CategoryFactory(parent=root, slug="kartoplya")
        another = CategoryFactory(parent=root, slug="another-crop")
        external = CategoryFactory(parent=root, slug="external-source")
        hub = CategoryHub.objects.create(category=potato, guide_category=external, market_category=external)
        other_hub = CategoryHub.objects.create(category=another)
        section = CategoryHubSection.objects.create(hub=hub, category=external, role="varieties")
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        executor.migrate([("classifier", "0018_categoryhub_market_category")])
        executor = MigrationExecutor(connection)
        target = [("classifier", "0019_category_hero_image_categoryhub_layout_and_more")]
        executor.migrate(target)
        apps = executor.loader.project_state(target).apps
        hub.refresh_from_db()
        other_hub.refresh_from_db()
        section.refresh_from_db()
        potato = apps.get_model("classifier", "Category").objects.get(pk=potato.pk)
        self.assertEqual(hub.layout, "sectioned")
        self.assertEqual(other_hub.layout, "standard")
        self.assertFalse(potato.hero_image)
        self.assertEqual((hub.guide_category_id, hub.market_category_id, section.category_id), (external.pk,) * 3)
        # Reversal removes presentation fields without deleting source records.
        MigrationExecutor(connection).migrate([("classifier", "0018_categoryhub_market_category")])
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state([("classifier", "0018_categoryhub_market_category")]).apps
        old_hub = old_apps.get_model("classifier", "CategoryHub").objects.get(pk=hub.pk)
        self.assertEqual((old_hub.guide_category_id, old_hub.market_category_id), (external.pk,) * 2)
        self.assertTrue(old_apps.get_model("classifier", "CategoryHubSection").objects.filter(pk=section.pk).exists())
