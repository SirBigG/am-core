from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType

from core.utils.tests.factories import UserFactory, PostFactory, CommentsFactory
from core.services.models import Comments

from rest_framework.test import APIClient, APITestCase

api_client = APIClient()


class PostCommentsTests(APITestCase):
    def setUp(self):
        self.post = PostFactory()
        self.user = UserFactory()
        admin = UserFactory(email='admin@agromega.in.ua')
        root = CommentsFactory(object_id=self.post.pk, content_type=ContentType.objects.get(model='post'),
                               user=admin, text='root')
        self.comment = CommentsFactory(object_id=self.post.pk, content_type=ContentType.objects.get(model='post'),
                                       user=self.user, text='comment text', parent=root)

    def test_get_node_list(self):
        response = api_client.get('/api/post/comments/',  {'post': self.post.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)
        # Test is_active False
        self.comment.is_active = False
        self.comment.save()
        response = api_client.get('/api/post/comments/', {'post': self.post.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 0)
        # Test without post parameter
        response = api_client.get('/api/post/comments/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 0)

    def test_get_detail_post(self):
        response = api_client.get('/api/post/comments/%s/' % self.comment.pk, {'post': self.post.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['object_id'], self.post.pk)
        # Test fields in response
        self.assertIn('pk', response.json())
        self.assertIn('object_id', response.json())
        self.assertIn('user_sign', response.json())
        self.assertIn('text', response.json())
        self.assertIn('creation', response.json())
        self.assertIn('parent', response.json())
        self.assertIn('level', response.json())

    def test_create_comment(self):
        p = PostFactory()
        # Test created not authenticated
        response = api_client.post('/api/post/comments/', {'object_id': p.pk,
                                                           'content_type': ContentType.objects.get(model='post'),
                                                           'user': self.user, 'text': 'comment text'})
        self.assertEqual(response.status_code, 403)
        # Test authenticate user
        api_client.force_authenticate(self.user)
        response = api_client.post('/api/post/comments/', {'object_id': p.pk,
                                                           'content_type': ContentType.objects.get(model='post'),
                                                           'user': self.user, 'text': 'comment text'})

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data)
        self.assertTrue(Comments.objects.get(object_id=p.pk, text='root'))

    # TODO create tests for update
