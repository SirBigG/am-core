import json
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from api.v1.content.tests import test_catalog_bulk as bulk_tests
from core.catalog.models import CatalogEntity
from core.catalog.relation_access import RelationAccess
from core.catalog.relations import EntityPresentationSelection, RelationRecord
from core.catalog.selection import _data_query, resolve_catalog_context, select_related_catalog
from core.catalog.tests import test_applications as application_tests
from core.classifier.publication_checks import SiteContentPolicy
from core.posts.models import Post
from core.posts.publication_checks import SitePostPublication


class SelectionTests(TestCase):
    setUp = application_tests.ApplicationTests.setUp
    participant = application_tests.ApplicationTests.participant
    grant_review = application_tests.ApplicationTests.grant_review
    grant_global_actions = application_tests.ApplicationTests.grant_global_actions
    approved_record = bulk_tests.ApplicationBulkTests.approved_record

    # CatalogFixtures helpers without inheriting all unrelated test cases.
    from api.v1.content.tests.test_catalog_relations import CatalogFixtures

    editor = staticmethod(CatalogFixtures.editor)
    publication_fixture = CatalogFixtures.publication_fixture
    publication_rights = CatalogFixtures.publication_rights
    setup_catalog = CatalogFixtures.setup_catalog
    create = CatalogFixtures.create
    action = CatalogFixtures.action

    def context(self, entity=None, **kwargs):
        return resolve_catalog_context(
            site=self.site,
            content_locale=kwargs.get("locale", "uk"),
            country=kwargs.get("country", "UA"),
            page_entity=entity or self.crop_entity.pk,
        )

    def config(self, **kwargs):
        return {
            "version": 1,
            "type": "plant_protection_application",
            "context_role": "crop",
            "result_role": "preparation",
            "filters": ["target", "method", "kind"],
            "sort": "canonical_title_uuid",
            "page_size": 20,
            **kwargs,
        }

    def select(self, **kwargs):
        return select_related_catalog(
            kwargs.pop("context", self.context()), kwargs.pop("config", self.config()), **kwargs
        )

    def test_live_release_no_writes_and_new_draft_retains_live_details(self):
        record = self.approved_record()
        with CaptureQueriesContext(connection) as captured:
            page = self.select()
        self.assertEqual(len(captured), 2)
        self.assertTrue(all(q["sql"].lstrip().startswith("SELECT") for q in captured))
        self.assertEqual(page["count"], 1)
        self.assertEqual(page["results"][0]["id"], str(self.preparation.pk))
        self.assertEqual(page["results"][0]["details"][0]["revision_id"], record["latest_revision"]["id"])
        self.draft["source"]["version"] = "pending"
        response = self.client.post(
            reverse("catalog-revisions", args=[record["id"]]),
            self.draft,
            format="json",
            headers={"if-match": record["etag"], "idempotency-key": "new-source"},
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.select(), page)

    def test_same_revision_counterexample_and_reverse_direction(self):
        self.approved_record()
        crop2 = self.participant("crop", "Other crop")
        target2 = self.participant("disease", "Other target")
        self.draft["participants"].update(crop=[str(crop2.pk)], target=[str(target2.pk)])
        self.approved_record("other-combination")
        self.assertEqual(self.select(filters={"target": [str(target2.pk)]})["count"], 0)
        self.assertEqual(self.select(filters={"target": [str(self.target.pk)]})["count"], 1)
        reverse_config = self.config(context_role="preparation", result_role="crop", filters=["target"])
        reverse = self.select(context=self.context(self.preparation.pk), config=reverse_config)
        self.assertEqual(reverse["count"], 2)
        self.assertEqual(self.select(context=self.context(crop2.pk), filters={"target": [str(target2.pk)]})["count"], 1)

    def test_dedup_details_facets_and_invalid_filters_do_not_broaden(self):
        self.approved_record()
        self.draft["payload"]["method"] = "soil_application"
        self.approved_record("soil")
        page = self.select()
        self.assertEqual(page["count"], 1)
        self.assertEqual(len(page["results"][0]["details"]), 2)
        self.assertEqual(len(page["facets"]["method"]), 2)
        filtered = self.select(filters={"method": "foliar_spray"})
        self.assertEqual(len(filtered["results"][0]["details"]), 1)
        self.assertEqual(self.select(filters={"method": "unknown"})["count"], 0)
        for bad in ({"other": "x"}, {"target": []}, {"target": ["bad"]}, {"method": {}}, {"kind": "bad"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                self.select(filters=bad)
        for config in (
            self.config(type={}),
            self.config(extra=True),
            self.config(context_role="missing"),
            self.config(page_size=21),
            self.config(filters=["sql"]),
            self.config(version=True),
        ):
            with self.assertRaises(ValidationError):
                self.select(config=config)
        with self.assertRaises(ValidationError):
            select_related_catalog(None, self.config())

    def test_fresh_visibility_and_material_guards_without_cache(self):
        self.approved_record()
        post = Post.objects.get(entity=self.preparation)
        selection = EntityPresentationSelection.objects.get(entity=self.target)
        mutations = [
            (Post.objects.filter(pk=post.pk), {"status": False}),
            (Post.objects.filter(pk=post.pk), {"text": "unreviewed replacement"}),
            (Post.objects.filter(pk=post.pk), {"publish_date": timezone.now() + timezone.timedelta(days=1)}),
            (SitePostPublication.objects.filter(post=post), {"enabled": False}),
            (
                SitePostPublication.objects.filter(post=post),
                {"publish_at": timezone.now() + timezone.timedelta(days=1)},
            ),
            (EntityPresentationSelection.objects.filter(pk=selection.pk), {"approved": False}),
            (type(self.root).objects.filter(pk=self.root.pk), {"is_active": False}),
            (SiteContentPolicy.objects.filter(site=self.site), {"active": False}),
            (CatalogEntity.objects.filter(pk=self.target.pk), {"state": "archived"}),
            (RelationRecord.objects.all(), {"archived": True}),
        ]
        for qs, values in mutations:
            with self.subTest(values=values), transaction.atomic():
                self.assertEqual(self.select()["count"], 1)
                qs.update(**values)
                hidden = self.select()
                self.assertEqual(hidden["count"], 0)
                self.assertEqual(hidden["facets"], {})
                transaction.set_rollback(True)
        Post.objects.filter(pk=post.pk).update(meta_title="SEO change")
        self.assertEqual(self.select()["count"], 1)
        self.assertEqual(self.select(context=self.context(locale="en"))["count"], 0)
        self.assertEqual(self.select(context=self.context(country="GB"))["count"], 0)
        foreign = type(self.site).objects.create(domain="selector.other", name="Other")
        other = resolve_catalog_context(
            site=foreign, content_locale="uk", country="UA", page_entity=self.crop_entity.pk
        )
        self.assertEqual(self.select(context=other)["count"], 0)

    def test_country_expiry_and_source_gate_are_synchronous(self):
        record = self.approved_record()
        details = self.select()["results"][0]["details"][0]
        end = timezone.datetime.fromisoformat(details["valid_until"] + "T23:59:59").replace(
            tzinfo=ZoneInfo(self.country.timezone_name)
        )
        with patch("core.catalog.selection.timezone.now", return_value=end):
            self.assertEqual(self.select()["count"], 1)
        with patch("core.catalog.selection.timezone.now", return_value=end + timezone.timedelta(seconds=1)):
            self.assertEqual(self.select()["count"], 0)
        self.grant_global_actions()
        access = RelationAccess(self.actor, self.site.pk)
        access.withdraw_application(
            record_id=record["id"],
            expected_version=record["lock_version"],
            operation_key="withdraw",
            reason="synthetic",
            evidence={"reason": "test"},
        )
        self.assertEqual(self.select()["count"], 0)

    def test_pagination_and_constant_query_budget(self):
        for i in range(25):
            self.preparation = self.participant("preparation", f"Equal title {i//2}")
            self.draft["participants"]["preparation"] = [str(self.preparation.pk)]
            self.approved_record(f"p{i}")
        config = self.config(page_size=5)
        ids, cursor = [], None
        for index in range(5):
            with CaptureQueriesContext(connection) as queries:
                page = self.select(config=config, **({"cursor": cursor} if cursor else {}))
            self.assertEqual(len(queries), 2)
            self.assertEqual(page["count"], 25)
            ids += [c["id"] for c in page["results"]]
            cursor = page["next_cursor"]
            if index == 0:
                for ctx in (self.context(country="GB"), self.context(self.target.pk)):
                    with self.assertRaises(ValidationError):
                        self.select(context=ctx, config=config, cursor=cursor)
                with self.assertRaises(ValidationError):
                    self.select(config=config, cursor=cursor + "bad")
        self.assertIsNone(cursor)
        self.assertEqual(len(set(ids)), 25)
        self.assertEqual([c["id"] for c in self.select()["results"]], ids[:20])
        sql, params = _data_query(self.context(), config, {})
        with connection.cursor() as db:
            db.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, params)
            plan = db.fetchone()[0]
        self.assertIn("Execution Time", plan[0])
        print("AGRO78_EXPLAIN25=" + json.dumps(plan))

    def test_generic_direct_reverse_and_symmetric_relations_share_policy(self):
        self.draft = {
            "type_code": "cultivar_of",
            "schema_version": 1,
            "participants": {"crop": [str(self.crop_entity.pk)], "cultivar": [str(self.cultivar_entity.pk)]},
            "payload": {},
            "source": {"citation": "synthetic"},
        }
        self.approved_record("generic")
        config = self.config(type="cultivar_of", result_role="cultivar", filters=["kind"])
        self.assertEqual(self.select(config=config)["results"][0]["id"], str(self.cultivar_entity.pk))
        reverse_config = {**config, "context_role": "cultivar", "result_role": "crop"}
        self.assertEqual(self.select(context=self.context(self.cultivar_entity.pk), config=reverse_config)["count"], 1)
        self.draft = {
            "type_code": "related_to",
            "schema_version": 1,
            "participants": {"member": [str(self.preparation.pk), str(self.target.pk)]},
            "payload": {},
            "source": {"citation": "synthetic"},
        }
        self.approved_record("symmetric")
        config = self.config(type="related_to", context_role="member", result_role="member", filters=["kind"])
        for own, other in ((self.preparation, self.target), (self.target, self.preparation)):
            self.assertEqual(
                self.select(context=self.context(own.pk), config=config)["results"][0]["id"], str(other.pk)
            )

    def test_legacy_und_never_infers_verified_language(self):
        from core.classifier.publication_checks import SiteCategoryConfiguration
        from core.posts.publication_checks import PostPublicationApproval, material_digest

        self.approved_record()
        for pub in SitePostPublication.objects.filter(site=self.site):
            post = Post.objects.get(pk=pub.post_id)
            approval = PostPublicationApproval.objects.create(
                post=post,
                content_locale="und",
                content_digest=material_digest(post),
                reviewed_by=self.actor,
                reviewed_at=timezone.now(),
                language_verified=False,
                legacy_published=True,
                legacy_site=self.site,
                provenance={"legacy": "synthetic"},
            )
            SitePostPublication.objects.filter(pk=pub.pk).update(approval=approval, content_locale="und")
        EntityPresentationSelection.objects.filter(site=self.site).update(content_locale="und")
        SiteCategoryConfiguration.objects.filter(site=self.site).update(content_locale="und")
        SiteContentPolicy.objects.filter(site=self.site).update(content_locales=["und"])
        ctx = self.context(locale="und")
        self.assertEqual(self.select(context=ctx)["count"], 0)
        SiteContentPolicy.objects.filter(site=self.site).update(allow_legacy_und=True)
        self.assertEqual(self.select(context=ctx)["count"], 1)
        self.assertEqual(self.select()["count"], 0)

    def test_source_quarantine_omits_other_sources_until_reconciled(self):
        from core.catalog.relation_service import reconcile_source_scope, withdraw_source
        from core.catalog.relations import RelationRevision, RelationScopeGate

        first = self.approved_record()
        self.draft["payload"]["method"] = "soil_application"
        self.draft["source"]["version"] = "2"
        self.approved_record("other-source")
        self.assertEqual(len(self.select()["results"][0]["details"]), 2)
        revision = RelationRevision.objects.get(pk=first["latest_revision"]["id"])
        withdraw_source(
            type_code="plant_protection_application",
            country="UA",
            digest=revision.source_version_digest,
            reason="synthetic",
            evidence={"review": "synthetic"},
            actor=self.actor,
            affected_versions={first["id"]: first["lock_version"]},
            scope_complete=False,
        )
        self.assertEqual(self.select()["count"], 0)
        scope = RelationScopeGate.objects.get()
        reconcile_source_scope(
            type_code="plant_protection_application",
            country="UA",
            expected_version=scope.lock_version,
            actor=self.actor,
            evidence={"review": "synthetic reconciliation"},
        )
        # Reconciliation does not republish or lift a source withdrawal.
        self.assertEqual(self.select()["count"], 0)

    def test_cursor_containers_raise_validation_without_queries(self):
        for cursor in ({":": 1}, [":"], {}, [], 1, True):
            with self.subTest(cursor=cursor), self.assertNumQueries(0), self.assertRaises(ValidationError):
                self.select(cursor=cursor)
