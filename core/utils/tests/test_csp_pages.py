from unittest.mock import patch

from django.contrib.sites.models import Site
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.diary.models import Diary, DiaryItem, Plant
from core.utils.tests.factories import (
    CategoryFactory,
    EventFactory,
    EventTypeFactory,
    LocationFactory,
    PostFactory,
    StaffUserFactory,
    UserFactory,
)


class ContentSecurityPolicyPublicPageTests(TestCase):
    header_name = "Content-Security-Policy-Report-Only"

    def assert_report_only_csp(self, response):
        self.assertIn(self.header_name, response.headers)
        policy = response.headers[self.header_name]
        self.assertIn("default-src 'self'", policy)
        self.assertIn("script-src 'self' 'unsafe-inline'", policy)
        self.assertIn("style-src 'self' 'unsafe-inline'", policy)
        self.assertIn("object-src 'none'", policy)

    def test_home_page_has_report_only_csp(self):
        parent = CategoryFactory()
        rubric = CategoryFactory(parent=parent)
        PostFactory.create_batch(2, rubric=rubric)

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "index.html")
        self.assert_report_only_csp(response)

    def test_post_detail_page_has_report_only_csp(self):
        parent = CategoryFactory()
        rubric = CategoryFactory(parent=parent)
        post = PostFactory(rubric=rubric)

        response = self.client.get(post.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/detail.html")
        self.assert_report_only_csp(response)

    def test_event_list_page_has_report_only_csp(self):
        EventFactory(status=1, start=timezone.now() + timezone.timedelta(days=1))

        response = self.client.get(reverse("events:event-list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/list.html")
        self.assert_report_only_csp(response)

    def test_event_form_page_has_report_only_csp_for_cdn_heavy_template(self):
        EventTypeFactory()
        LocationFactory()

        response = self.client.get(reverse("events:event-form"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/form.html")
        self.assert_report_only_csp(response)

    def test_login_page_has_report_only_csp_for_auth_template(self):
        response = self.client.get("/login/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pro_auth/login.html")
        self.assert_report_only_csp(response)

    def test_feedback_page_has_report_only_csp_for_recaptcha_template(self):
        response = self.client.get("/feedback/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "services/feedback.html")
        self.assert_report_only_csp(response)

    @override_settings(API_HOST="https://api.example.com")
    @patch("core.news.views.requests.get")
    def test_news_list_page_has_report_only_csp_for_external_image_template(self, mocked_get):
        mocked_get.return_value.status_code = 200
        mocked_get.return_value.json.return_value = {
            "items": [
                {
                    "data": {
                        "title": "Market update",
                        "image": "https://cdn.example.com/news.webp",
                        "link": "https://example.com/news",
                    },
                    "created": "2026-05-12",
                }
            ],
            "previous": None,
            "next": None,
        }

        response = self.client.get(reverse("news:news-list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "news/list.html")
        self.assert_report_only_csp(response)
        self.assertIn("img-src 'self' data: https: http:", response.headers[self.header_name])


class ContentSecurityPolicyAuthenticatedPageTests(TestCase):
    header_name = "Content-Security-Policy-Report-Only"

    def setUp(self):
        self.user = UserFactory()
        self.category = CategoryFactory(slug="basil", value="Базилік")
        self.plant = Plant.objects.create(user=self.user, category=self.category, variety="Genovese")
        self.diary = Diary.objects.create(user=self.user, title="Diary", description="desc")
        self.diary.plants.set([self.plant])
        self.diary_item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="note",
            description="Листя виглядає добре",
            date="2026-04-24",
        )
        self.diary_item.plants.set([self.plant])
        self.client.force_login(self.user)

    def assert_report_only_csp(self, response):
        self.assertIn(self.header_name, response.headers)
        policy = response.headers[self.header_name]
        self.assertIn("default-src 'self'", policy)
        self.assertIn("script-src 'self' 'unsafe-inline'", policy)
        self.assertIn("style-src 'self' 'unsafe-inline'", policy)
        self.assertIn("object-src 'none'", policy)

    def test_profile_dashboard_has_report_only_csp(self):
        response = self.client.get(reverse("pro_auth:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pro_auth/profile/dashboard.html")
        self.assert_report_only_csp(response)

    def test_profile_diary_list_has_report_only_csp(self):
        response = self.client.get(reverse("pro_auth:profile-diary-list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "diary/profile/diary_list.html")
        self.assert_report_only_csp(response)

    def test_profile_diary_detail_has_report_only_csp_for_interactive_template(self):
        response = self.client.get(self.diary.get_profile_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "diary/profile/diary_detail.html")
        self.assert_report_only_csp(response)

    def test_profile_diary_item_form_has_report_only_csp_for_ckeditor_template(self):
        response = self.client.get(reverse("pro_auth:profile-diary-item-add", kwargs={"diary_id": self.diary.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "diary/profile/diary_item_form.html")
        self.assert_report_only_csp(response)

    def test_django_admin_login_has_report_only_csp(self):
        self.client.logout()
        Site.objects.update_or_create(
            id=1,
            defaults={"domain": "localhost:8000", "name": "localhost"},
        )

        response = self.client.get("/admin/login/", {"next": "/admin/"}, HTTP_HOST="localhost:8000")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/login.html")
        self.assert_report_only_csp(response)

    def test_django_admin_index_has_report_only_csp_for_staff_user(self):
        staff_user = StaffUserFactory(is_superuser=True)
        self.client.force_login(staff_user)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/index.html")
        self.assert_report_only_csp(response)
