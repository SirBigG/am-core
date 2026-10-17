from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from core.classifier.models import Category, CategoryPresentationMode
from core.posts.guide_hub import get_public_guide_sections
from core.posts.models import GuideSection, GuideSectionArticle, Post
from core.utils.tests.factories import CategoryFactory, PostFactory


class PublicGuideCollectionTests(TestCase):
    def setUp(self):
        self.root = CategoryFactory()
        self.crop = CategoryFactory(parent=self.root)
        self.hub = CategoryFactory(parent=self.crop, presentation_mode=CategoryPresentationMode.GUIDE_HUB)
        self.owner_root = CategoryFactory()
        self.owner_parent = CategoryFactory(parent=self.owner_root)
        self.owner = CategoryFactory(parent=self.owner_parent)
        self.post = PostFactory(rubric=self.owner)
        self.section = GuideSection.objects.create(category=self.hub, title="Planting")
        self.placement = GuideSectionArticle.objects.create(section=self.section, post=self.post)

    def test_returns_existing_post_from_another_category(self):
        sections = get_public_guide_sections(self.hub.pk)
        self.assertEqual(sections, [self.section])
        self.assertEqual(sections[0].public_articles, [self.placement])
        self.assertEqual(sections[0].public_articles[0].post, self.post)

    def test_orders_sections_and_placements_by_position_then_pk(self):
        earlier = GuideSection.objects.create(category=self.hub, title="Planning", sort_order=0)
        self.section.sort_order = 10
        self.section.save()
        later = GuideSection.objects.create(category=self.hub, title="Storage", sort_order=10)
        for section in (earlier, later):
            GuideSectionArticle.objects.create(section=section, post=self.post)
        self.placement.sort_order = 20
        self.placement.save()
        first = GuideSectionArticle.objects.create(
            section=self.section, post=PostFactory(rubric=self.owner), sort_order=10
        )
        second = GuideSectionArticle.objects.create(
            section=self.section, post=PostFactory(rubric=self.owner), sort_order=10
        )
        sections = get_public_guide_sections(self.hub.pk)
        self.assertEqual(sections, [earlier, self.section, later])
        self.assertEqual(sections[1].public_articles, [first, second, self.placement])

    def test_inactive_sections_are_excluded(self):
        GuideSection.objects.filter(pk=self.section.pk).update(is_active=False)
        self.assertEqual(get_public_guide_sections(self.hub.pk), [])

    def test_inactive_articles_are_excluded_and_empty_sections_omitted(self):
        active = PostFactory(rubric=self.owner)
        placement = GuideSectionArticle.objects.create(section=self.section, post=active)
        Post.objects.filter(pk=self.post.pk).update(status=False)
        GuideSection.objects.create(category=self.hub, title="Empty")
        self.assertEqual(get_public_guide_sections(self.hub.pk)[0].public_articles, [placement])
        Post.objects.filter(pk=active.pk).update(status=False)
        self.assertEqual(get_public_guide_sections(self.hub.pk), [])

    def test_inactive_hub_or_any_ancestor_excludes_collection(self):
        for category in (self.hub, self.crop, self.root):
            with self.subTest(category=category.pk):
                Category.objects.filter(pk=category.pk).update(is_active=False)
                self.assertEqual(get_public_guide_sections(self.hub.pk), [])
                Category.objects.filter(pk=category.pk).update(is_active=True)

    def test_inactive_article_category_or_any_ancestor_excludes_placement(self):
        for category in (self.owner, self.owner_parent, self.owner_root):
            with self.subTest(category=category.pk):
                Category.objects.filter(pk=category.pk).update(is_active=False)
                self.assertEqual(get_public_guide_sections(self.hub.pk), [])
                Category.objects.filter(pk=category.pk).update(is_active=True)

    def test_ancestry_checks_support_deeper_trees(self):
        deep_owner = CategoryFactory(parent=CategoryFactory(parent=self.owner))
        Post.objects.filter(pk=self.post.pk).update(rubric=deep_owner)
        self.assertEqual(len(get_public_guide_sections(self.hub.pk)), 1)
        Category.objects.filter(pk=self.owner_root.pk).update(is_active=False)
        self.assertEqual(get_public_guide_sections(self.hub.pk), [])

    def test_inactive_siblings_and_other_trees_do_not_hide_eligible_posts(self):
        CategoryFactory(parent=self.owner_parent, is_active=False)
        CategoryFactory(parent=self.crop, is_active=False)
        CategoryFactory(is_active=False)
        self.assertEqual(get_public_guide_sections(self.hub.pk)[0].public_articles, [self.placement])

    def test_only_requested_category_is_returned_and_reuse_is_preserved(self):
        other_hub = CategoryFactory(presentation_mode=CategoryPresentationMode.GUIDE_HUB)
        other_section = GuideSection.objects.create(category=other_hub, title="Other hub")
        other_placement = GuideSectionArticle.objects.create(section=other_section, post=self.post)
        self.assertEqual(get_public_guide_sections(self.hub.pk), [self.section])
        self.assertEqual(get_public_guide_sections(other_hub.pk)[0].public_articles, [other_placement])

    def test_missing_category_returns_empty_collection(self):
        self.assertEqual(get_public_guide_sections(-1), [])

    def test_visibility_changes_are_reflected_on_each_call(self):
        self.assertEqual(len(get_public_guide_sections(self.hub.pk)), 1)
        Post.objects.filter(pk=self.post.pk).update(status=False)
        self.assertEqual(get_public_guide_sections(self.hub.pk), [])
        Post.objects.filter(pk=self.post.pk).update(status=True)
        self.assertEqual(len(get_public_guide_sections(self.hub.pk)), 1)
        Category.objects.filter(pk=self.hub.pk).update(is_active=False)
        self.assertEqual(get_public_guide_sections(self.hub.pk), [])
        Category.objects.filter(pk=self.hub.pk).update(is_active=True)
        self.assertEqual(len(get_public_guide_sections(self.hub.pk)), 1)

    def test_presentation_mode_does_not_define_collection_eligibility(self):
        Category.objects.filter(pk=self.hub.pk).update(presentation_mode=CategoryPresentationMode.CATALOG)
        self.assertEqual(get_public_guide_sections(self.hub.pk), [self.section])

    def test_reads_do_not_generate_urls_or_modify_articles(self):
        Post.objects.filter(pk=self.post.pk).update(absolute_url="")
        original = Post.objects.values().get(pk=self.post.pk)
        with CaptureQueriesContext(connection) as queries:
            sections = get_public_guide_sections(self.hub.pk)
            self.assertEqual(sections[0].public_articles[0].post.absolute_url, "")
        self.assertTrue(all(query["sql"].lstrip().upper().startswith("SELECT") for query in queries))
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), original)

    def test_query_count_stays_constant_as_collection_grows(self):
        def read_collection():
            with self.assertNumQueries(2):
                sections = get_public_guide_sections(self.hub.pk)
                return [
                    (section.title, item.post.title, item.post.absolute_url, item.post.rubric.value)
                    for section in sections
                    for item in section.public_articles
                ]

        self.assertEqual(len(read_collection()), 1)
        for index in range(8):
            section = GuideSection.objects.create(category=self.hub, title=f"Stage {index}")
            for post in (self.post, PostFactory(rubric=self.owner)):
                GuideSectionArticle.objects.create(section=section, post=post)
        self.assertEqual(len(read_collection()), 17)
