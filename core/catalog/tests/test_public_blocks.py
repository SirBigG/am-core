from urllib.parse import urlsplit

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from core.catalog.relation_access import RelationAccess
from core.classifier.publication_checks import SiteCategoryConfiguration
from core.posts.models import GuideSection, GuideSectionArticle, Post
from core.posts.templatetags.post_extras import full_url

from . import test_blocks


class PublicBlockFixtures:
    def setUp(self):
        test_blocks.BlockTests.setUp(self)
        config = override_settings(RELATED_CATALOG_MARKETS={self.site.pk: "UA"})
        config.enable()
        self.addCleanup(config.disable)
        cache.clear()
        self.addCleanup(cache.clear)
        self.category.refresh_from_db()
        self.path = self.category.absolute_url
        SiteCategoryConfiguration.objects.filter(site=self.site, category=self.category).update(
            canonical_path=self.path
        )
        self.anonymous = self.client_class()
        self.blocks[0]["page_size"] = 1

    publication_fixture = test_blocks.BlockTests.publication_fixture
    publication_rights = test_blocks.BlockTests.publication_rights
    setup_catalog = test_blocks.BlockTests.setup_catalog
    editor = staticmethod(test_blocks.BlockTests.editor)
    setUp_application = test_blocks.BlockTests.setUp_application
    participant = test_blocks.BlockTests.participant
    approved_record = test_blocks.BlockTests.approved_record
    grant_review = test_blocks.BlockTests.grant_review
    grant_global_actions = test_blocks.BlockTests.grant_global_actions
    create = test_blocks.BlockTests.create
    action = test_blocks.BlockTests.action
    save = test_blocks.BlockTests.save
    activate = test_blocks.BlockTests.activate

    def api_url(self, anchor=None):
        return reverse("public-related-catalog", args=["post" if anchor else "category", (anchor or self.category).pk])


class PublicBlockTests(PublicBlockFixtures, TestCase):
    def test_crop_filters_paging_noindex_and_detail_context(self):
        self.approved_record()
        first = self.preparation
        other = self.participant("preparation", "Synthetic formulation B")
        self.draft["participants"]["preparation"] = [str(other.pk)]
        self.approved_record("second-preparation")
        self.activate(self.save())
        html = self.anonymous.get(self.path)
        self.assertContains(html, "Synthetic preparations")
        self.assertContains(html, "Наступна сторінка")
        self.assertContains(html, "Проблема")
        self.assertIn("no-store", html["Cache-Control"])

        api = self.anonymous.get(self.api_url())
        result = api.json()["blocks"][0]
        self.assertEqual(result["selection"]["count"], 2)
        self.assertEqual(result["selection"]["results"][0]["id"], str(first.pk))
        next_query = urlsplit(result["next_url"]).query
        next_page = self.anonymous.get(self.api_url() + "?" + next_query)
        self.assertEqual(next_page.json()["blocks"][0]["selection"]["results"][0]["id"], str(other.pk))
        filtered = self.anonymous.get(self.path, {"catalog_1_target": str(self.target.pk)})
        self.assertContains(filtered, 'name="robots" content="noindex,follow"')
        self.assertContains(filtered, f'rel="canonical" href="{full_url(self.path)}"')
        self.assertContains(filtered, "Скинути фільтри")
        invalid = self.anonymous.get(self.api_url(), {"catalog_1_target": "invalid"})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["blocks"], [])
        foreign = self.anonymous.get(self.api_url(), {"country": "GB"})
        self.assertEqual(foreign.status_code, 400)
        self.assertEqual(foreign.json()["blocks"], [])
        href = result["selection"]["results"][0]["href"]
        self.assertIn("catalog_crop=", href)
        self.assertContains(self.anonymous.get(href), "Застосування для")
        problem = Post.objects.get(entity=self.target)
        self.assertContains(self.anonymous.get(problem.absolute_url), "Synthetic preparations")
        self.assertEqual(self.anonymous.get(self.api_url(problem)).json()["blocks"][0]["selection"]["count"], 2)
        Post.objects.filter(pk=problem.pk).update(status=False)
        self.assertEqual(self.anonymous.get(self.api_url(problem)).json()["blocks"], [])
        self.assertEqual(self.anonymous.get(self.api_url()).json()["blocks"], [])

    def test_manual_slot_remains_owned_when_empty_and_restores_on_disable(self):
        from django.contrib.auth.models import Permission

        self.actor.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="posts",
                codename__in=["view_post", "view_guidesection", "view_guidesectionarticle"],
            )
        )
        guide = GuideSection.objects.create(category=self.category, title="Retained editorial placement")
        placement = GuideSectionArticle.objects.create(section=guide, post=self.post)
        record = self.approved_record()
        self.assertContains(self.anonymous.get(self.path), guide.title)
        self.blocks[0].update(manual_replacement="guide_placements", manual_ids=[placement.pk])
        config = self.activate(self.save())
        activated = self.anonymous.get(self.path)
        self.assertNotContains(activated, guide.title)
        self.assertContains(activated, self.blocks[0]["title"])
        self.grant_global_actions()
        actor = type(self.actor).objects.get(pk=self.actor.pk)
        RelationAccess(actor, self.site.pk).withdraw_application(
            record_id=record["id"],
            expected_version=record["lock_version"],
            reason="Synthetic",
            evidence={"review": "synthetic"},
            operation_key="public-render-withdraw",
        )
        after = self.anonymous.get(self.path)
        self.assertNotContains(after, guide.title)
        self.assertNotContains(after, self.blocks[0]["title"])
        self.access.disable(self.hub.pk, "uk", config.lock_version)
        self.assertContains(self.anonymous.get(self.path), guide.title)
        self.assertTrue(GuideSectionArticle.objects.filter(pk=placement.pk, post=self.post).exists())

    def test_cultivar_requires_explicit_live_crop_link(self):
        self.approved_record()
        self.activate(self.save())
        page = self.post.absolute_url
        self.assertNotContains(self.anonymous.get(page), "Для культури")
        self.draft = dict(
            type_code="cultivar_of",
            schema_version=1,
            participants={"crop": [str(self.crop_entity.pk)], "cultivar": [str(self.cultivar_entity.pk)]},
            payload={},
            source={},
        )
        self.approved_record("cultivar-scope")
        self.assertContains(self.anonymous.get(page), "Для культури Fixture crop")

    def test_second_crop_choice_and_same_application_filters(self):
        from core.catalog.access_models import RelationEntityGrant
        from core.catalog.relations import EntityPresentationSelection
        from core.classifier.models import CategoryHub
        from core.utils.tests.factories import CategoryFactory

        self.approved_record()
        self.activate(self.save())
        crop = self.participant("crop", "Second crop identity")
        category = CategoryFactory(parent=self.root, entity=crop, value="Second crop")
        category.refresh_from_db()
        SiteCategoryConfiguration.objects.create(
            site=self.site, category=category, content_locale="uk", visible=True, canonical_path=category.absolute_url
        )
        EntityPresentationSelection.objects.filter(entity=crop).update(post=None, category=category)
        RelationEntityGrant.objects.filter(entity=crop).update(post=None, category=category)
        hub = CategoryHub.objects.create(category=category, is_active=True, site=self.site, locale="uk")
        self.draft["participants"]["crop"] = [str(crop.pk)]
        self.draft["payload"]["method"] = "soil_application"
        self.approved_record("second-crop")
        config = self.access.save(hub.pk, "uk", self.blocks, None)
        preview = self.access.preview(hub.pk, "uk", config.revisions.get().pk, "UA")
        self.access.activate(hub.pk, "uk", config.lock_version, preview["preview"])
        target = Post.objects.get(entity=self.target)
        api = self.api_url(target)
        no_scope = self.anonymous.get(api).json()
        self.assertEqual(no_scope["blocks"], [])
        self.assertEqual({c["id"] for c in no_scope["crop_choices"]}, {str(crop.pk), str(self.crop_entity.pk)})
        selected = self.anonymous.get(api, {"catalog_crop": str(crop.pk)}).json()
        self.assertEqual(selected["blocks"][0]["selection"]["results"][0]["method_labels"], ["Ґрунтове внесення"])
        wrong_method = self.anonymous.get(api, {"catalog_crop": str(crop.pk), "catalog_1_method": "foliar_spray"})
        self.assertEqual(wrong_method.json()["blocks"][0]["selection"]["count"], 0)
        self.assertContains(self.anonymous.get(category.absolute_url), "Synthetic preparations")

    def test_method_filter_is_preserved_from_problem_card_to_detail(self):
        self.approved_record()
        alternative = self.participant("preparation", "Different soil preparation")
        self.draft["participants"]["preparation"] = [str(alternative.pk)]
        self.draft["payload"]["method"] = "soil_application"
        self.approved_record("soil-application")
        self.blocks += [
            {**self.blocks[0], "slot": "crop.related_problems", "title": "Related problems", "result_role": "target"}
        ]
        self.activate(self.save())
        original = self.anonymous.get(self.api_url(), {"catalog_2_method": "foliar_spray"}).json()
        problem = next(block for block in original["blocks"] if block["slot"] == "crop.related_problems")
        link = problem["selection"]["results"][0]["href"]
        detail = self.anonymous.get(link)
        self.assertContains(detail, "Synthetic formulation A")
        section = detail.content.decode().split('id="related-catalog-1"', 1)[1].split("</section>", 1)[0]
        self.assertNotIn("Different soil preparation", section)
        linked_post = Post.objects.get(entity=self.target)
        result = self.anonymous.get(self.api_url(linked_post) + "?" + urlsplit(link).query).json()
        self.assertEqual(result["blocks"][0]["selection"]["count"], 1)

    def test_multipage_preview_survives_cursor_timestamp_change(self):
        from unittest.mock import patch

        self.approved_record()
        other = self.participant("preparation", "Synthetic formulation B")
        self.draft["participants"]["preparation"] = [str(other.pk)]
        self.approved_record("more-than-one-page")
        config = self.save()
        with patch("django.core.signing.time.time", return_value=1_800_000_000):
            plan = self.access.preview(self.hub.pk, "uk", config.revisions.get().pk, "UA")
        self.assertTrue(plan["blocks"][0]["selection"]["next_cursor"])
        with patch("django.core.signing.time.time", return_value=1_800_000_005):
            active = self.access.activate(self.hub.pk, "uk", config.lock_version, plan["preview"])
        self.assertTrue(active.enabled)

    def test_problem_link_preserves_multiple_fixed_preparations(self):
        self.approved_record()
        approved = [str(self.preparation.pk)]
        for index in (2, 3):
            entity = self.participant("preparation", f"Formulation {index}")
            self.draft["participants"]["preparation"] = [str(entity.pk)]
            self.approved_record(f"alternative-{index}")
            if index == 2:
                approved.append(str(entity.pk))
        self.blocks[0]["filters"].append("preparation")
        self.blocks += [
            {
                **self.blocks[0],
                "slot": "crop.related_problems",
                "result_role": "target",
                "conditions": {"preparation": approved},
            }
        ]
        self.activate(self.save())
        crop = self.anonymous.get(self.api_url()).json()
        block = next(block for block in crop["blocks"] if block["slot"] == "crop.related_problems")
        link = block["selection"]["results"][0]["href"]
        target = Post.objects.get(entity=self.target)
        detail = self.anonymous.get(self.api_url(target) + "?" + urlsplit(link).query).json()["blocks"][0]
        self.assertEqual(detail["selection"]["count"], 2)
        self.assertEqual(detail["preserved"]["catalog_1_preparation"], ",".join(approved))
