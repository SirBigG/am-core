from __future__ import unicode_literals

from django.test import TestCase, Client, RequestFactory

from utils.tests.factories import PostFactory, CategoryFactory, PhotoFactory, \
    UserFactory

from factory import build_batch

from rest_framework.test import APITestCase, APIClient

from appl.posts.models import Photo

api_client = APIClient()

client = Client()

request = RequestFactory()


class MainPageTest(TestCase):

    def test_response(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)


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
        PostFactory(rubric=self.post.rubric, status=0)
        response = client.get('/' + self.parent.slug + '/')
        self.assertEqual(len(response.context['object_list']), 3)
        self.assertEqual(response.context['title'], self.parent.value)

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
        self.assertEqual(response.context['title'], self.post.rubric.value)

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


class ApiPostListTests(APITestCase):
    def setUp(self):
        for i in range(5):
            post = PostFactory()
            PhotoFactory(post=post)

    def tearDown(self):
        for i in Photo.objects.all():
            i.delete()

    def test_response(self):
        response = api_client.get('/api/post/all/')
        self.assertEqual(response.status_code, 200)

    def test_pagination(self):
        PostFactory.create_batch(20)
        PostFactory(status=0)
        response = api_client.get('/api/post/all/', format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(response.data['count'], 25)
        self.assertEqual(response.data['next'], 'http://testserver/api/post/all/?page=2')
        response = api_client.get('/api/post/all/?page=2', format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 10)


class RandomApiPostListTests(APITestCase):
    def setUp(self):
        PostFactory.create_batch(7)

    def test_response(self):
        response = api_client.get('/api/post/random/all/', format='json')
        self.assertEqual(response.status_code, 200)

    def test_pagination(self):
        response = api_client.get('/api/post/random/all/', format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 4)
        self.assertEqual(response.data['count'], 7)
        self.assertEqual(response.data['next'], 'http://testserver/api/post/random/all/?page=2')
        response = api_client.get('/api/post/random/all/?page=2', format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 3)


class UserPostsViewSetTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.user.set_password('12345')
        self.user.save()
        self.post = PostFactory(publisher=self.user)

    def test_return_post(self):
        api_client.login(email=self.user.email, password='12345')
        response = api_client.get('/posts/user/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)

    def test_not_autorized(self):
        response = api_client.get('/posts/user/')
        self.assertEqual(response.status_code, 403)

    def test_detail_post(self):
        api_client.login(email=self.user.email, password='12345')
        response = api_client.get('/posts/user/%s/' % self.post.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn('title', response.data)
        self.assertIn('text', response.data)
        self.assertIn('photo', response.data)
        self.assertTrue(response.data['status'])

    # TODO: create this test
    # TODO: more tests for view set
    """
    def test_creating_post_by_user(self):
        rubric = CategoryFactory()
        api_client.login(email=self.user.email, password='12345')
        response = api_client.post('/posts/user/', data={'title': 'title', 'text': 'text',
                                                         'photo': 'photo', 'rubric': rubric.pk,
                                                         'publisher': self.user.pk})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Post.objects.filter(publisher=self.user).count(), 2)
        # response = client.get(response.data['url'])
        # self.assertEqual(response.status_code, 200)
    """
