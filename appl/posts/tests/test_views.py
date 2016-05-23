# -*- coding: utf-8 -*-

from django.test import TestCase, Client, RequestFactory
from django.core.cache import cache
from django.utils.cache import get_cache_key

from utils.tests.factories import PostFactory, CategoryFactory

from factory import build_batch

client = Client()

request = RequestFactory()


class MainPageTest(TestCase):

    def test_response(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_caching(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        req = request.get('/')
        key = get_cache_key(req, key_prefix='index_')
        self.assertTrue(cache.get(key))


class PostListTests(TestCase):

    def setUp(self):
        self.parent = CategoryFactory()
        self.category = CategoryFactory(parent=self.parent)
        self.post = PostFactory(rubric=self.category)

    def test_parent_list(self):
        response = client.get('/' + self.parent.slug + '/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['object_list']), 1)
        PostFactory(rubric=self.post.rubric)
        PostFactory(rubric=self.post.rubric)
        response = client.get('/' + self.parent.slug + '/')
        self.assertEqual(len(response.context['object_list']), 3)

    def test_parent_list_404(self):
        response = client.get('/unknown/')
        self.assertEqual(response.status_code, 404)

    def test_child_list(self):
        slug = self.post.rubric.slug
        response = client.get('/' + self.parent.slug + '/' + slug + '/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'posts/list.html')
        self.assertEqual(len(response.context['object_list']), 1)
        PostFactory(rubric=self.post.rubric)
        PostFactory(rubric=self.post.rubric)
        response = client.get('/' + self.parent.slug + '/' + slug + '/')
        self.assertEqual(len(response.context['object_list']), 3)
        self.assertEqual(len(response.context['menu_items']), 1)

    def test_child_list_404(self):
        response = client.get('/' + self.parent.slug + '/unknown/')
        self.assertEqual(response.status_code, 404)

    def test_list_pagination(self):
        build_batch(PostFactory, 21, rubric=self.category)
        response = client.get('/' + self.parent.slug + '/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['page_obj'].has_next())
        self.assertFalse(response.context['page_obj'].has_previous())
        self.assertEqual(response.context['page_obj'].next_page_number(), 2)
        self.assertEqual(response.context['page_obj'].number, 1)
        self.assertEqual(response.context['paginator'].num_pages, 2)
        response = client.get('/' + self.parent.slug + '/?page=2')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['page_obj'].has_next())
        self.assertTrue(response.context['page_obj'].has_previous())
        self.assertEqual(response.context['page_obj'].previous_page_number(), 1)
        self.assertEqual(response.context['page_obj'].number, 2)


class PostDetailTests(TestCase):

    def setUp(self):
        self.parent = CategoryFactory()
        child = CategoryFactory(parent=self.parent)
        self.category = CategoryFactory(parent=child)
        self.post = PostFactory(rubric=self.category)

    def test_detail(self):
        response = client.get(self.post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'posts/detail.html')
        self.assertIn('object', response.context)
        self.assertEqual(len(response.context['menu_items']), 1)

    def test_detail_caching(self):
        req = request.get(self.post.get_absolute_url())
        response = client.get(self.post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        key = get_cache_key(req, 'post_')
        self.assertTrue(cache.get(key))


class SiteMapTests(TestCase):
    def setUp(self):
        PostFactory.create_batch(5)

    def test_return_context(self):
        response = client.get('/sitemap.xml/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['base'], 'http://agromega.in.ua/')
        self.assertEqual(len(response.context['urls']), 5)
        self.assertTemplateUsed(response, 'sitemap.xml')


class ErrorsHandlerTests(TestCase):

    def test_404_handler_using(self):
        response = client.get('/sdg/sdg/dfdg')
        self.assertTemplateUsed(response, '404.html')
        self.assertTemplateUsed(response, 'header.html')
        self.assertTemplateUsed(response, 'footer.html')

    # TODO: create test for 500 handler
