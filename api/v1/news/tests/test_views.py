import json

from rest_framework.test import APITestCase

from core.news.models import News


class CreateNewsViewTests(APITestCase):

    def test_post_request(self):
        response = self.client.post('/api/news/',
                                    data=json.dumps({"items": [{"title": "Title", "link": "http://aaa.aa/aaa"},
                                                               {"title": "Title2", "link": "http://aaa.aa/aaa2"}]}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("link", response.json())
        self.assertEqual(News.objects.count(), 2)
