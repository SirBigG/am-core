from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.utils.tests.factories import CategoryFactory, EventFactory, EventTypeFactory, LocationFactory, PostFactory


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
        policy = response.headers[self.header_name]
        self.assertIn("https://code.jquery.com", policy)
        self.assertIn("https://cdnjs.cloudflare.com", policy)
        self.assertIn("https://stackpath.bootstrapcdn.com", policy)

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
        policy = response.headers[self.header_name]
        self.assertIn("https://www.google.com", policy)
        self.assertIn("https://www.gstatic.com", policy)

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
