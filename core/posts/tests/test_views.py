from __future__ import unicode_literals

from django.test import TestCase, Client, RequestFactory

from core.utils.tests.factories import PostFactory, CategoryFactory, MetaDataFactory
from core.utils.tests.utils import HtmlTestCaseMixin

from factory import build_batch


client = Client()

request = RequestFactory()


class MainPageTest(TestCase):

    def test_response(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)


class PostListTests(HtmlTestCaseMixin, TestCase):

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
        PostFactory(rubric=self.post.rubric, status=0)
        response = client.get('/' + self.parent.slug + '/')
        self.assertEqual(len(response.context['object_list']), 3)
        self.assertEqual(response.context['category'], self.parent)

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
        self.assertEqual(response.context['category'], self.post.rubric)

    def test_child_list_404(self):
        response = client.get('/' + self.parent.slug + '/unknown/')
        self.assertEqual(response.status_code, 404)

    def test_list_pagination(self):
        build_batch(PostFactory, 21, rubric=self.category)
        response = client.get('/' + self.parent.slug + '/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'posts/list.html')
        self.assertTemplateUsed(response, 'helpers/pagination.html')
        self.assertTrue(response.context['page_obj'].has_next())
        self.assertFalse(response.context['page_obj'].has_previous())
        self.assertEqual(response.context['page_obj'].next_page_number(), 2)
        self.assertEqual(response.context['page_obj'].number, 1)
        self.assertEqual(response.context['paginator'].num_pages, 2)
        self.assertIn(b'pagination', response.content)
        response = client.get('/' + self.parent.slug + '/?page=2')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'posts/list.html')
        self.assertTemplateUsed(response, 'helpers/pagination.html')
        self.assertFalse(response.context['page_obj'].has_next())
        self.assertTrue(response.context['page_obj'].has_previous())
        self.assertEqual(response.context['page_obj'].previous_page_number(), 1)
        self.assertEqual(response.context['page_obj'].number, 2)
        self.assertIn(b'pagination', response.content)

    def test_meta_data(self):
        meta = MetaDataFactory()
        self.parent.meta = meta
        self.parent.save()
        response = client.get('/' + self.parent.slug + '/')
        self.assertEqual(response.status_code, 200)
        self.assertMetaDataIn(response.content)
        self.assertH1(response.content)
        self.assertClassIn('list-h1', response.content)
        self.assertEqualTitleValue(response.content, 'title | AgroMega.in.ua')
        self.assertEqualMetaTagContent(response.content, 'description', 'description')


class PostDetailTests(HtmlTestCaseMixin, TestCase):

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

    def test_meta_data(self):
        response = client.get(self.post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertMetaDataIn(response.content)
        self.assertH1(response.content)


class SiteMapTests(TestCase):
    def setUp(self):
        root = CategoryFactory()
        parent = CategoryFactory(parent=root)
        child = CategoryFactory(parent=parent)
        PostFactory.create_batch(5, **{'rubric': child})

    def test_return_context(self):
        response = client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['base'], 'https://agromega.in.ua/')
        self.assertEqual(len(response.context['urls']), 5)
        self.assertTemplateUsed(response, 'sitemap.xml')


class ErrorsHandlerTests(TestCase):

    def test_404_handler_using(self):
        response = client.get('/sdg/sdg/dfdg')
        self.assertTemplateUsed(response, '404.html')
        self.assertTemplateUsed(response, 'header.html')
        self.assertTemplateUsed(response, 'footer.html')

    # TODO: create test for 500 handler
