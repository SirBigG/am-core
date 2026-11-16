import uuid

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models import ProtectedError
from django.test import TestCase, TransactionTestCase

from core.catalog.models import CatalogEntity, CatalogEntityKind
from core.utils.tests.factories import CategoryFactory, PostFactory, UserFactory


class CatalogEntityTests(TestCase):
    def test_posts_can_share_a_protected_identity(self):
        author = UserFactory()
        entity = CatalogEntity.objects.create(
            kind=CatalogEntityKind.CULTIVAR, provenance={"source": "fixture"}, created_by=author
        )
        posts = [PostFactory(publisher=author, entity=entity) for _ in range(2)]
        self.assertCountEqual(entity.posts.all(), posts)
        self.assertIsNone(PostFactory().entity_id)
        with self.assertRaises(ProtectedError):
            entity.delete()

    def test_database_guards_stable_uuid_and_kind(self):
        entity = CatalogEntity.objects.create(
            kind=CatalogEntityKind.CROP, provenance={"source": "fixture"}, created_by=UserFactory()
        )
        for fields in ({"id": uuid.uuid4()}, {"kind": "unknown"}, {"state": "unknown"}, {"version": 0}):
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                CatalogEntity.objects.filter(pk=entity.pk).update(**fields)
        entity.refresh_from_db()
        self.assertEqual(entity.kind, CatalogEntityKind.CROP)


class CatalogEntityMigrationTests(TransactionTestCase):
    def test_additive_migration_preserves_posts_and_references(self):
        before = [("posts", "0035_guide_hub_foundation"), ("catalog", None)]
        after = [("posts", "0036_post_entity")]
        author = UserFactory()
        category = CategoryFactory()
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        executor.migrate(before)
        historical = [(app, name) for app, name in leaves if app in {"companies", "registry"}]
        historical += [("posts", "0035_guide_hub_foundation"), ("classifier", "0020_category_url_redirect")]
        apps = executor.loader.project_state(historical).apps
        Post = apps.get_model("posts", "Post")
        post = Post.objects.create(
            title="Fixture",
            text="Original",
            slug="original",
            absolute_url="/original-1.html",
            rubric_id=category.pk,
            publisher_id=author.pk,
        )
        Company = apps.get_model("companies", "Company")
        company = Company.objects.create(name="Fixture", website="https://example.com", location_id=author.location_id)
        product = apps.get_model("companies", "Product").objects.create(company_id=company.pk, post_id=post.pk)
        variety = apps.get_model("registry", "Variety").objects.create(
            title="Fixture",
            slug="fixture",
            publication_id=post.pk,
        )
        original = Post.objects.values().get(pk=post.pk)

        for targets, upgraded in ((after, True), (before, False), (after, True)):
            executor = MigrationExecutor(connection)
            executor.migrate(targets)
            graph = historical + after if upgraded else historical
            apps = executor.loader.project_state(graph).apps
            observed = apps.get_model("posts", "Post").objects.values().get(pk=post.pk)
            if upgraded:
                self.assertIsNone(observed.pop("entity_id"))
                self.assertFalse(apps.get_model("catalog", "CatalogEntity").objects.exists())
            self.assertEqual(observed, original)
            self.assertEqual(apps.get_model("companies", "Product").objects.get(pk=product.pk).post_id, post.pk)
            self.assertEqual(apps.get_model("registry", "Variety").objects.get(pk=variety.pk).publication_id, post.pk)
