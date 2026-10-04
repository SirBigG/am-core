from django.contrib.auth.models import Permission
from django.http import QueryDict
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from core.posts.category_attribute_filters import apply_category_attribute_filters
from core.posts.models import Post, PostAttributeValue
from core.utils.tests.factories import (
    CategoryAttributeChoiceFactory,
    CategoryAttributeFieldFactory,
    CategoryFactory,
    UserFactory,
)


class ContentAttributeTests(APITestCase):
    def setUp(self):
        self.user = UserFactory(is_staff=True)
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.category = CategoryFactory()
        self.field = CategoryAttributeFieldFactory(category=self.category, key="ripening", field_type="select")
        self.choice = CategoryAttributeChoiceFactory(field=self.field, value="early", label="Ранній")

    def create_post(self, attributes):
        return self.client.post(
            "/api/content/posts/",
            {
                "title": "Test variety",
                "text": "Body",
                "rubric": self.category.pk,
                "category_attributes": attributes,
            },
            format="json",
        )

    def test_create_indexes_attributes_and_public_filter_finds_post(self):
        result = self.create_post({str(self.category.pk): {"ripening": "early"}})
        self.assertEqual(result.status_code, 201, result.data)
        post = Post.objects.get(pk=result.data["id"])
        self.assertTrue(PostAttributeValue.objects.filter(post=post, choice=self.choice).exists())
        filtered = apply_category_attribute_filters(Post.objects.all(), self.category, QueryDict("attr_ripening=early"))
        self.assertEqual(list(filtered.values_list("pk", flat=True)), [post.pk])

    def test_unknown_choices_and_wrong_category_are_rejected_without_post(self):
        for attrs in (
            {str(self.category.pk): {"ripening": "unknown"}},
            {"999999": {"ripening": "early"}},
            {str(self.category.pk): {"unknown": "early"}},
        ):
            response = self.create_post(attrs)
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Post.objects.exists())

    def test_patch_replaces_current_values_and_clears_index(self):
        result = self.create_post({str(self.category.pk): {"ripening": "early"}})
        pk = result.data["id"]
        response = self.client.patch(f"/api/content/posts/{pk}/", {"category_attributes": {}}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(PostAttributeValue.objects.filter(post_id=pk).exists())

    def test_editorial_only_patch_preserves_attributes_and_indexes(self):
        result = self.create_post({str(self.category.pk): {"ripening": "early"}})
        pk = result.data["id"]
        response = self.client.patch(f"/api/content/posts/{pk}/", {"title": "Edited"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["category_attributes"], {str(self.category.pk): {"ripening": "early"}})
        self.assertTrue(PostAttributeValue.objects.filter(post_id=pk).exists())

    def test_unknown_boolean_is_omitted_and_false_remains_false(self):
        CategoryAttributeFieldFactory(category=self.category, key="resistant", field_type="boolean")
        for raw in ("false", 0, 1):
            response = self.create_post({str(self.category.pk): {"resistant": raw}})
            self.assertEqual(response.status_code, 400, response.data)
        response = self.create_post({str(self.category.pk): {"resistant": False}})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIs(PostAttributeValue.objects.get(post_id=response.data["id"]).value_boolean, False)

    def test_reversed_range_and_nonfinite_number_are_rejected(self):
        CategoryAttributeFieldFactory(category=self.category, key="weight", field_type="range", decimal_places=2)
        for value in ({"min": "100", "max": "50"}, {"min": "NaN"}, {"min": "Infinity"}, {"min": True}):
            response = self.create_post({str(self.category.pk): {"weight": value}})
            self.assertEqual(response.status_code, 400, response.data)

    def test_schema_exposes_fields_choices_and_stable_checksum(self):
        url = f"/api/content/categories/{self.category.pk}/schema/"
        first = self.client.get(url)
        second = self.client.get(url)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data["checksum"], second.data["checksum"])
        self.assertEqual(first.data["fields"][0]["choices"][0]["value"], "early")

    def test_schema_writes_require_model_permission_and_never_allow_delete(self):
        data = {"category": self.category.pk, "key": "new-field", "label": "New", "field_type": "boolean"}
        denied = self.client.post("/api/content/attribute-fields/", data, format="json")
        self.assertEqual(denied.status_code, 403)
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_categoryattributefield", content_type__app_label="posts")
        )
        allowed = self.client.post("/api/content/attribute-fields/", data, format="json")
        self.assertEqual(allowed.status_code, 201, allowed.data)
        response = self.client.delete(f"/api/content/attribute-fields/{allowed.data['id']}/")
        self.assertIn(response.status_code, (403, 405))

    def test_used_field_identity_cannot_change(self):
        self.create_post({str(self.category.pk): {"ripening": "early"}})
        self.user.user_permissions.add(
            Permission.objects.get(codename="change_categoryattributefield", content_type__app_label="posts")
        )
        response = self.client.patch(
            f"/api/content/attribute-fields/{self.field.pk}/", {"key": "renamed"}, format="json"
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.field.refresh_from_db()
        self.assertEqual(self.field.key, "ripening")
