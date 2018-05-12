from datetime import datetime, timedelta

from django.test import TestCase

from core.utils.tests.factories import NewsFactory
from core.utils.tests.utils import DisableAutoAdd

from core.news.models import News


class NewsListViewTests(TestCase):
    def test_empty_response(self):
        response = self.client.get('/news/list/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('object_list', response.context)
        self.assertTemplateUsed(response, 'news/list.html')

    def test_with_filter(self):
        with DisableAutoAdd(*(News,)):
            NewsFactory.create_batch(10, date=datetime.now() - timedelta(hours=2))
            response = self.client.get(f'/news/list/?from={int((datetime.now() - timedelta(hours=1)).timestamp())}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.context['object_list']), 0)
            self.assertEqual(response.context["paginator"].num_pages, 1)
            self.assertTemplateUsed(response, 'news/list.html')
