from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.posts.category_attributes import normalize_range_value, rebuild_post_attribute_values
from core.posts.models import CategoryAttributeFieldType, PostAttributeValue
from core.utils.tests.factories import (
    CategoryAttributeChoiceFactory,
    CategoryAttributeFieldFactory,
    CategoryFactory,
    PostFactory,
)


class CategoryAttributeRangeTests(TestCase):
    def test_normalize_range_value_supports_exact_value(self):
        self.assertEqual(normalize_range_value("220"), {"min": "220", "max": "220"})

    def test_normalize_range_value_supports_maximum_only(self):
        self.assertEqual(normalize_range_value("max 220"), {"max": "220"})

    def test_normalize_range_value_supports_minimum_only(self):
        self.assertEqual(normalize_range_value("from 120"), {"min": "120"})

    def test_normalize_range_value_supports_interval(self):
        self.assertEqual(normalize_range_value("100-150"), {"min": "100", "max": "150"})


class PostAttributeValueIndexTests(TestCase):
    def test_rebuild_post_attribute_values_indexes_current_category_interval(self):
        category = CategoryFactory()
        field = CategoryAttributeFieldFactory(
            category=category,
            key="fruit_weight",
            field_type=CategoryAttributeFieldType.RANGE,
        )
        post = PostFactory(
            rubric=category,
            category_attributes={str(category.pk): {"fruit_weight": {"min": "100", "max": "150"}}},
        )

        rebuild_post_attribute_values(post)

        value = PostAttributeValue.objects.get(post=post, field=field)
        self.assertEqual(value.value_number_min, Decimal("100"))
        self.assertEqual(value.value_number_max, Decimal("150"))

    def test_rebuild_post_attribute_values_ignores_stored_data_for_other_categories(self):
        current_category = CategoryFactory()
        old_category = CategoryFactory()
        CategoryAttributeFieldFactory(
            category=current_category,
            key="current",
            field_type=CategoryAttributeFieldType.RANGE,
        )
        CategoryAttributeFieldFactory(
            category=old_category,
            key="old",
            field_type=CategoryAttributeFieldType.RANGE,
        )
        post = PostFactory(
            rubric=current_category,
            category_attributes={
                str(current_category.pk): {"current": {"max": "220"}},
                str(old_category.pk): {"old": {"min": "100", "max": "150"}},
            },
        )

        rebuild_post_attribute_values(post)

        self.assertEqual(PostAttributeValue.objects.filter(post=post).count(), 1)
        self.assertEqual(PostAttributeValue.objects.get(post=post).field.key, "current")

    def test_rebuild_post_attribute_values_command_rebuilds_existing_posts(self):
        category = CategoryFactory(slug="apples")
        field = CategoryAttributeFieldFactory(category=category, key="ripening")
        choice = CategoryAttributeChoiceFactory(field=field, value="winter", label="Winter")
        post = PostFactory(
            rubric=category,
            category_attributes={str(category.pk): {"ripening": choice.value}},
        )
        PostAttributeValue.objects.filter(post=post).delete()

        output = StringIO()
        call_command("rebuild_post_attribute_values", category="apples", stdout=output)

        self.assertIn("Rebuilt attribute values for 1 posts.", output.getvalue())
        self.assertTrue(PostAttributeValue.objects.filter(post=post, field=field, choice=choice).exists())
