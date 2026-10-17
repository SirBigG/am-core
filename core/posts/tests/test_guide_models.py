from django.db import IntegrityError, transaction
from django.test import TestCase

from core.classifier.models import CategoryPresentationMode
from core.posts.models import GuideSection, GuideSectionArticle, Post
from core.utils.tests.factories import CategoryFactory, PostFactory


class GuideSectionTests(TestCase):
    def setUp(self):
        self.category = CategoryFactory(presentation_mode=CategoryPresentationMode.GUIDE_HUB)

    def section(self, **kwargs):
        return GuideSection.objects.create(category=self.category, title="Planting", **kwargs)

    def test_multiple_empty_sections_allow_duplicate_titles(self):
        first = self.section()
        second = self.section()
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(list(self.category.guide_sections.all()), [first, second])
        self.assertEqual(first.description, "")
        self.assertTrue(first.is_active)
        self.assertFalse(first.articles.exists())

    def test_section_order_uses_position_then_primary_key(self):
        last = self.section(sort_order=20)
        first = self.section(sort_order=10)
        second = self.section(sort_order=10)
        self.assertEqual(list(self.category.guide_sections.all()), [first, second, last])

    def test_section_title_can_change_without_changing_identity(self):
        section = self.section()
        section.title = "Seed preparation"
        section.is_active = False
        section.save()
        section.refresh_from_db()
        self.assertEqual(section.title, "Seed preparation")
        self.assertFalse(section.is_active)
        self.assertEqual(self.category.guide_sections.get().pk, section.pk)


class GuideSectionArticleTests(TestCase):
    def setUp(self):
        root = CategoryFactory()
        crop = CategoryFactory(parent=root)
        self.owner = CategoryFactory(parent=crop)
        self.post = PostFactory(rubric=self.owner, text="Original body", status=False)
        self.post.get_absolute_url()
        self.post.refresh_from_db()
        self.original = Post.objects.values().get(pk=self.post.pk)
        self.hub = CategoryFactory(presentation_mode=CategoryPresentationMode.GUIDE_HUB)
        self.section = GuideSection.objects.create(category=self.hub, title="Planting")

    def assert_post_unchanged(self):
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original)

    def test_post_can_be_reused_in_sections_and_other_hubs(self):
        other_hub = CategoryFactory(presentation_mode=CategoryPresentationMode.GUIDE_HUB)
        sections = [
            self.section,
            GuideSection.objects.create(category=self.hub, title="Care"),
            GuideSection.objects.create(category=other_hub, title="Planning"),
        ]
        for section in sections:
            GuideSectionArticle.objects.create(section=section, post=self.post)
        self.assertEqual(self.post.guide_placements.count(), 3)
        self.assert_post_unchanged()

    def test_duplicate_post_in_section_is_rejected_by_database(self):
        GuideSectionArticle.objects.create(section=self.section, post=self.post)
        with self.assertRaises(IntegrityError), transaction.atomic():
            GuideSectionArticle.objects.create(section=self.section, post=self.post, sort_order=10)
        self.assertEqual(self.section.articles.count(), 1)

    def test_placement_order_uses_position_then_primary_key(self):
        last = GuideSectionArticle.objects.create(section=self.section, post=self.post, sort_order=20)
        first = GuideSectionArticle.objects.create(
            section=self.section, post=PostFactory(rubric=self.owner), sort_order=10
        )
        second = GuideSectionArticle.objects.create(
            section=self.section, post=PostFactory(rubric=self.owner), sort_order=10
        )
        self.assertEqual(list(self.section.articles.all()), [first, second, last])

    def test_creating_reordering_and_deleting_placement_preserves_article(self):
        placement = GuideSectionArticle.objects.create(section=self.section, post=self.post)
        self.assert_post_unchanged()
        placement.sort_order = 9
        placement.save()
        self.assert_post_unchanged()
        placement.delete()
        self.assertFalse(self.section.articles.exists())
        self.assert_post_unchanged()

    def test_deleting_section_removes_placements_but_preserves_article(self):
        GuideSectionArticle.objects.create(section=self.section, post=self.post)
        self.section.delete()
        self.assertFalse(self.post.guide_placements.exists())
        self.assert_post_unchanged()

    def test_deleting_hub_preserves_article_owned_by_another_category(self):
        GuideSectionArticle.objects.create(section=self.section, post=self.post)
        self.hub.delete()
        self.assertFalse(GuideSection.objects.filter(pk=self.section.pk).exists())
        self.assertFalse(self.post.guide_placements.exists())
        self.assert_post_unchanged()

    def test_deleting_article_removes_placements_but_preserves_section(self):
        GuideSectionArticle.objects.create(section=self.section, post=self.post)
        self.post.delete()
        self.assertTrue(GuideSection.objects.filter(pk=self.section.pk).exists())
        self.assertFalse(self.section.articles.exists())
