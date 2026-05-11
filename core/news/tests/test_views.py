from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse


class NewsResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload or {}

    def json(self):
        return self.payload


@override_settings(API_HOST="https://api.example.com")
class NewsListViewTests(TestCase):
    @patch("core.news.views.requests.get")
    def test_renders_news_list_from_api(self, mocked_get):
        mocked_get.return_value = NewsResponse(
            payload={
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
                "next": "https://api.example.com/news?page=2",
            }
        )

        response = self.client.get(reverse("news:news-list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "news/list.html")
        self.assertEqual(len(response.context["object_list"]), 1)
        self.assertTrue(response.context["page_obj"]["has_next"])
        mocked_get.assert_called_once_with("https://api.example.com/news")

    @patch("core.news.views.requests.get")
    def test_renders_empty_list_when_api_fails(self, mocked_get):
        mocked_get.return_value = NewsResponse(status_code=500)

        response = self.client.get(reverse("news:news-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["object_list"], [])


@override_settings(API_HOST="https://api.example.com", HOST="example.com")
class NewsDetailViewTests(TestCase):
    @patch("core.news.views.requests.get")
    def test_renders_news_detail_from_api(self, mocked_get):
        mocked_get.return_value = NewsResponse(
            payload={
                "title": "Market update",
                "description": "<p>News body</p>",
                "image": "",
                "created": "2026-05-12",
            }
        )

        response = self.client.get(reverse("news:news-detail", kwargs={"slug": "market-update", "pk": 12}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "news/detail.html")
        self.assertEqual(response.context["object"]["title"], "Market update")
        self.assertEqual(response.context["object"]["url"], "example.com/news/market-update-12.html")
        mocked_get.assert_called_once_with("https://api.example.com/news/12")

    @patch("core.news.views.requests.get")
    def test_returns_404_when_api_returns_not_found(self, mocked_get):
        mocked_get.return_value = SimpleNamespace(status_code=404)

        response = self.client.get(reverse("news:news-detail", kwargs={"slug": "missing", "pk": 404}))

        self.assertEqual(response.status_code, 404)
