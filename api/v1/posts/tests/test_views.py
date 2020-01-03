from core.utils.tests.factories import PostFactory, CategoryFactory, PhotoFactory, \
    UserFactory
from core.utils.tests.utils import make_image

from rest_framework.test import APITestCase, APIClient

from core.posts.models import Photo, Post
from core.classifier.models import Category

api_client = APIClient()


class ApiPostListTests(APITestCase):
    def setUp(self):
        root = CategoryFactory()
        parent = CategoryFactory(parent=root)
        self.child = CategoryFactory(parent=parent)
        for i in range(5):
            post = PostFactory(rubric=self.child)
            PhotoFactory(post=post)

    def tearDown(self):
        for i in Photo.objects.all():
            i.delete()

    def test_response(self):
        response = api_client.get('/api/post/all/')
        self.assertEqual(response.status_code, 200)

    def test_pagination(self):
        PostFactory.create_batch(20, **{'rubric': self.child})
        PostFactory(status=0, rubric=self.child)
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
        root = CategoryFactory()
        parent = CategoryFactory(parent=root)
        child = CategoryFactory(parent=parent)
        PostFactory.create_batch(7, **{'rubric': child})

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
        root = CategoryFactory()
        parent = CategoryFactory(parent=root)
        child = CategoryFactory(parent=parent)
        self.post = PostFactory(publisher=self.user, rubric=child)

    def test_return_post(self):
        api_client.login(email=self.user.email, password='12345')
        response = api_client.get('/api/user/posts/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)

    def test_not_autorized(self):
        response = api_client.get('/api/user/posts/')
        self.assertEqual(response.status_code, 403)

    def test_detail_post(self):
        PhotoFactory(post=self.post)
        api_client.login(email=self.user.email, password='12345')
        response = api_client.get('/api/user/posts/%s/' % self.post.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn('title', response.data)
        self.assertIn('text', response.data)
        self.assertIn('photo', response.data)
        self.assertTrue(response.data['status'])

    def test_creating_post_by_user(self):
        root = CategoryFactory()
        parent = CategoryFactory(parent=root, slug='pigeon')
        api_client.login(email=self.user.email, password='12345')
        response = api_client.post('/api/user/posts/', data=dict(title=u'тайтл',
                                                                 text='text',
                                                                 photos=[make_image(), make_image()],
                                                                 rubric=parent.pk))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Post.objects.filter(publisher=self.user).count(), 2)
        self.assertEqual(Post.objects.get(title=u'тайтл').slug, 'tajtl')
        self.assertEqual(Post.objects.get(title=u'тайтл').status, 0)
        self.assertEqual(Photo.objects.count(), 2)
        # Test creating user category for parent
        self.assertTrue(Category.objects.get(slug="pigeon-user"))
        # Test returns url for created post
        response = api_client.get(response.data['url'])
        self.assertEqual(response.status_code, 200)


class PostViewTests(APITestCase):
    def setUp(self):
        self.post = PostFactory()

    def test_create_view_instance(self):
        self.assertEqual(Post.objects.get(pk=self.post.pk).hits, 0)
        response = self.client.post('/api/post/view/', data={"fingerprint": "fingerprint", "post_id": self.post.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.get(pk=self.post.pk).hits, 1)
        # Test second time not inc counter
        response = self.client.post('/api/post/view/', data={"fingerprint": "fingerprint", "post_id": self.post.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.get(pk=self.post.pk).hits, 1)
