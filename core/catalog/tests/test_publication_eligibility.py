from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from time import monotonic, sleep

from django.contrib.sites.models import Site
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from core.catalog.models import CatalogEntity
from core.catalog.publication_eligibility import PublicationUnavailable, eligible_participant_urls
from core.catalog.relations import EntityPresentationSelection
from core.classifier.publication_checks import SiteCategoryConfiguration, SiteContentPolicy
from core.posts.publication_checks import PostPublicationApproval, SitePostPublication, material_digest
from core.utils.tests.factories import CategoryFactory, PostFactory, UserFactory


class PublicationEligibilityTests(TestCase):
    def setUp(self):
        self.actor = UserFactory()
        self.site = Site.objects.create(domain="publication.example.test", name="Fixture")
        self.policy = SiteContentPolicy.objects.create(site=self.site, active=True, content_locales=["uk", "und"])
        self.root = CategoryFactory()
        self.category = CategoryFactory(parent=self.root)
        self.crop = CatalogEntity.objects.create(kind="crop", created_by=self.actor, provenance={"fixture": True})
        type(self.category).objects.filter(pk=self.category.pk).update(entity=self.crop)
        self.category.refresh_from_db()
        self.configs = [
            SiteCategoryConfiguration.objects.create(
                site=self.site, category=c, content_locale="uk", visible=True, canonical_path=f"/category-{c.pk}/"
            )
            for c in (self.root, self.category)
        ]
        self.entity = CatalogEntity.objects.create(kind="cultivar", created_by=self.actor, provenance={"fixture": True})
        self.post = PostFactory(entity=self.entity, rubric=self.category)
        self.post.get_absolute_url()
        self.post.refresh_from_db()
        self.approval = PostPublicationApproval.objects.create(
            post=self.post,
            content_locale="uk",
            content_digest=material_digest(self.post),
            reviewed_by=self.actor,
            reviewed_at=timezone.now(),
            language_verified=True,
            provenance={"fixture": True},
        )
        self.publication = SitePostPublication.objects.create(
            site=self.site,
            post=self.post,
            approval=self.approval,
            content_locale="uk",
            category=self.category,
            canonical_path=self.post.absolute_url,
            enabled=True,
            publish_at=timezone.now(),
        )
        for entity, anchor in ((self.entity, {"post": self.post}), (self.crop, {"category": self.category})):
            EntityPresentationSelection.objects.create(
                site=self.site, entity=entity, content_locale="uk", approved=True, updated_by=self.actor, **anchor
            )

    def urls(self, **kwargs):
        return eligible_participant_urls(
            site_id=self.site.pk, content_locale="uk", entity_ids=[self.entity.pk, self.crop.pk], **kwargs
        )

    def test_current_publications_and_crop_category_are_explicitly_scoped(self):
        expected = {self.entity.pk: self.post.absolute_url, self.crop.pk: self.configs[-1].canonical_path}
        self.assertEqual(self.urls(), expected)
        self.assertEqual(self.urls(lock=True), expected)
        other = Site.objects.create(domain="foreign.example.test", name="Other")
        for site_id, locale in ((other.pk, "uk"), (self.site.pk, "en")):
            with self.assertRaises(PublicationUnavailable):
                eligible_participant_urls(site_id=site_id, content_locale=locale, entity_ids=[self.entity.pk])
        SiteContentPolicy.objects.filter(pk=self.site.pk).update(active=False)
        with self.assertRaises(PublicationUnavailable):
            self.urls()

    def test_changed_content_invalidates_evidence_but_seo_only_keeps_it(self):
        type(self.post).objects.filter(pk=self.post.pk).update(meta_title="SEO only")
        self.assertIn(self.entity.pk, self.urls())
        type(self.post).objects.filter(pk=self.post.pk).update(text="Unreviewed replacement")
        with self.assertRaises(PublicationUnavailable):
            self.urls()

    def test_hidden_ancestor_future_post_and_disabled_publication_are_rejected(self):
        cases = [
            (type(self.root).objects.filter(pk=self.root.pk), {"is_active": False}),
            (SiteCategoryConfiguration.objects.filter(pk=self.configs[0].pk), {"visible": False}),
            (type(self.post).objects.filter(pk=self.post.pk), {"status": False}),
            (
                type(self.post).objects.filter(pk=self.post.pk),
                {"publish_date": timezone.now() + timezone.timedelta(days=1)},
            ),
            (SitePostPublication.objects.filter(pk=self.publication.pk), {"enabled": False}),
            (
                SitePostPublication.objects.filter(pk=self.publication.pk),
                {"publish_at": timezone.now() + timezone.timedelta(days=1)},
            ),
            (EntityPresentationSelection.objects.filter(entity=self.entity), {"approved": False}),
        ]
        for queryset, fields in cases:
            with self.subTest(fields=fields), transaction.atomic():
                queryset.update(**fields)
                with self.assertRaises(PublicationUnavailable):
                    self.urls()
                transaction.set_rollback(True)

    def test_immutable_approval_and_mismatched_language_cannot_be_written(self):
        for query, fields in [
            (PostPublicationApproval.objects.filter(pk=self.approval.pk), {"language_verified": False}),
            (SitePostPublication.objects.filter(pk=self.publication.pk), {"content_locale": "en"}),
        ]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                query.update(**fields)

    def test_legacy_und_needs_explicit_publication_and_opt_in(self):
        approval = PostPublicationApproval.objects.create(
            post=self.post,
            content_locale="und",
            content_digest=material_digest(self.post),
            reviewed_by=self.actor,
            reviewed_at=timezone.now(),
            legacy_published=True,
            legacy_site=self.site,
            provenance={"legacy": True},
        )
        # Move the explicit publication and selection to und; UI language is irrelevant.
        SitePostPublication.objects.filter(pk=self.publication.pk).update(approval=approval, content_locale="und")
        EntityPresentationSelection.objects.filter(entity=self.entity).update(content_locale="und")
        SiteCategoryConfiguration.objects.filter(site=self.site).update(content_locale="und")
        kwargs = {"site_id": self.site.pk, "content_locale": "und", "entity_ids": [self.entity.pk]}
        with self.assertRaises(PublicationUnavailable):
            eligible_participant_urls(**kwargs)
        SiteContentPolicy.objects.filter(site=self.site).update(allow_legacy_und=True)
        self.assertEqual(eligible_participant_urls(**kwargs), {self.entity.pk: self.post.absolute_url})

    def test_unknown_language_evidence_stays_on_its_original_site(self):
        approval = PostPublicationApproval.objects.create(
            post=self.post,
            content_locale="und",
            content_digest=material_digest(self.post),
            reviewed_by=self.actor,
            reviewed_at=timezone.now(),
            legacy_published=True,
            legacy_site=self.site,
            provenance={"legacy": True},
        )
        foreign = Site.objects.create(domain="foreign-legacy.example.test", name="Foreign")
        SiteContentPolicy.objects.create(site=foreign, active=True, content_locales=["und"], allow_legacy_und=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SitePostPublication.objects.create(
                site=foreign,
                post=self.post,
                approval=approval,
                content_locale="und",
                category=self.category,
                canonical_path=self.post.absolute_url,
                enabled=True,
                publish_at=timezone.now(),
            )
        with self.assertRaises(PublicationUnavailable):
            eligible_participant_urls(site_id=foreign.pk, content_locale="und", entity_ids=[self.entity.pk])


class PublicationSelectionLockTests(TransactionTestCase):
    setUp = PublicationEligibilityTests.setUp

    def _exercise(self, *, selection_first):
        from core.catalog.publication_eligibility import lock_publication_graph
        from core.catalog.relation_service import set_presentation_selection

        selection = EntityPresentationSelection.objects.get(entity=self.entity)
        pids = Queue()

        def read():
            return eligible_participant_urls(
                site_id=self.site.pk, content_locale="uk", entity_ids=[self.entity.pk], lock=True
            )

        def write():
            set_presentation_selection(
                site=self.site,
                content_locale="uk",
                entity=self.entity,
                anchor=self.post,
                expected_version=selection.lock_version,
                actor=self.actor,
                approved=True,
            )

        def worker():
            close_old_connections()
            try:
                with transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout='7s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put(cursor.fetchone()[0])
                    (read if selection_first else write)()
                return "committed"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic(), connection.cursor() as cursor:
                if selection_first:
                    lock_publication_graph()
                    type(self.post).objects.select_for_update().get(pk=self.post.pk)
                else:
                    read()
                future = pool.submit(worker)
                pid = pids.get(timeout=5)
                deadline = monotonic() + 5
                while True:
                    cursor.execute("SELECT pg_backend_pid()=ANY(pg_blocking_pids(%s))", [pid])
                    if cursor.fetchone()[0]:
                        break
                    if future.done() or monotonic() > deadline:
                        self.fail("Concurrent selection/eligibility did not wait on the common anchor")
                    sleep(0.01)
                if selection_first:
                    write()
            self.assertEqual(future.result(timeout=8), "committed")

    def test_selection_writer_first_serializes_eligibility(self):
        self._exercise(selection_first=True)

    def test_eligibility_first_serializes_selection_writer(self):
        self._exercise(selection_first=False)
