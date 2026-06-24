from django.contrib import admin
from django.test import RequestFactory, TestCase
from django.utils import timezone

from core.posts.admin import PostAdmin
from core.posts.models import Post
from core.utils.tests.factories import CategoryFactory, StaffUserFactory


class PostAdminAppleAttributesTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().post("/")
        self.request.user = StaffUserFactory()
        self.model_admin = PostAdmin(Post, admin.site)
        self.apple_parent = CategoryFactory(slug="yabluni", value="Яблуні")
        self.apple_rubric = CategoryFactory(slug="sorty-yablun", value="Сорти яблунь", parent=self.apple_parent)
        self.other_rubric = CategoryFactory(slug="sorty-ogirkiv", value="Сорти огірків")

    def get_form(self, rubric, **attribute_values):
        form_class = self.model_admin.get_form(self.request)
        now = timezone.now()
        data = {
            "title": "Ред Делішес",
            "text": "Опис сорту",
            "slug": "red-delishes",
            "rubric": rubric.pk,
            "publisher": self.request.user.pk,
            "publish_date_0": now.strftime("%Y-%m-%d"),
            "publish_date_1": now.strftime("%H:%M:%S"),
            "update_date_0": now.strftime("%Y-%m-%d"),
            "update_date_1": now.strftime("%H:%M:%S"),
            "status": "on",
            "tags": "",
            **attribute_values,
        }
        return form_class(data=data)

    def test_saves_apple_attributes_for_apple_variety_rubric(self):
        form = self.get_form(
            self.apple_rubric,
            apple_attribute_ripening_period="winter",
            apple_attribute_fruit_color=["red"],
            apple_attribute_taste=["sweet_tart", "dessert"],
            apple_attribute_pollination="needs_pollinator",
        )

        self.assertTrue(form.is_valid(), form.errors)
        post = form.save(commit=False)
        self.model_admin.save_model(self.request, post, form, change=False)

        self.assertEqual(
            post.apple_attributes,
            {
                "ripening_period": "winter",
                "fruit_color": ["red"],
                "taste": ["sweet_tart", "dessert"],
                "pollination": "needs_pollinator",
            },
        )

    def test_clears_apple_attributes_for_other_rubrics(self):
        form = self.get_form(
            self.other_rubric,
            apple_attribute_ripening_period="winter",
            apple_attribute_fruit_color=["red"],
        )

        self.assertTrue(form.is_valid(), form.errors)
        post = form.save(commit=False)
        self.model_admin.save_model(self.request, post, form, change=False)

        self.assertEqual(post.apple_attributes, {})
