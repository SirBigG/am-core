from unittest.mock import patch

from django.test import TestCase, Client
from django.contrib.contenttypes.models import ContentType

from core.utils.tests.factories import UserFactory, CategoryFactory, ReviewsFactory

client = Client()


class FeedbackViewTests(TestCase):

    def test_get_response(self):
        response = client.get('/feedback/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'services/feedback.html')

    @patch("django_recaptcha.fields.client.submit")
    def test_post_success_response(self, mock_submit):
        response = client.post('/feedback/', {'title': 'feed title', 'email': 'test@test.com',
                                              'text': 'feed text', "g-recaptcha-response": "PASSED"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'services/success.html')
        mock_submit.assert_called_once()


class IsReviewedTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.category = CategoryFactory(slug='test_slug')
        self.category.save()

    def test_response_not_authorized(self):
        response = self.client.get('/service/reviews/is-reviewed/', data={'slug': 'test_slug'},
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 403)

    def test_authorized_without_review(self):
        self.client.force_login(self.user)
        response = self.client.get('/service/reviews/is-reviewed/', data={'slug': 'test_slug'},
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['is-reviewed'], 0)
        self.assertEqual(response.json()['is-valid'], 0)

    def test_authorized_with_review(self):
        self.client.force_login(self.user)
        self.category.is_for_user = True
        self.category.save()
        cat = CategoryFactory(parent=self.category, slug='valid-slug')
        ReviewsFactory(user=self.user, content_type=ContentType.objects.get(model='category'),
                       object_id=cat.pk)
        response = self.client.get('/service/reviews/is-reviewed/', data={'slug': 'valid-slug'},
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['is-reviewed'], 1)
        self.assertEqual(response.json()['is-valid'], 1)

    def test_not_ajax_response(self):
        self.client.force_login(self.user)
        ReviewsFactory(user=self.user, content_type=ContentType.objects.get(model='reviews'),
                       object_id=self.category.pk)
        response = self.client.get('/service/reviews/is-reviewed/', data={'slug': 'test_slug'},)
        self.assertEqual(response.status_code, 404)


class ReviewsListsViewTests(TestCase):
    def test_list_response(self):
        category = CategoryFactory(slug='list_slug')
        category.save()
        ReviewsFactory.create_batch(3, object_id=category.pk, content_type=ContentType.objects.get(model='category'),
                                    user=UserFactory())
        response = self.client.get('/service/reviews/category/list_slug-%s/' % category.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['object_list']), 3)
        self.assertTemplateUsed(response, 'services/reviews/list.html')
        response = self.client.get('/service/reviews/category/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['object_list']), 3)

    def test_all_reviews(self):
        user = UserFactory()
        category = CategoryFactory(slug='list_slug')
        category.save()
        category2 = CategoryFactory(slug='list_slug2')
        category2.save()
        ReviewsFactory.create_batch(3, object_id=category.pk, content_type=ContentType.objects.get(model='category'),
                                    user=user)
        ReviewsFactory.create_batch(3, object_id=category2.pk, content_type=ContentType.objects.get(model='category'),
                                    user=user)
        response = self.client.get('/service/reviews/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['object_list']), 6)
        self.assertTemplateUsed(response, 'services/reviews/list.html')

    def test_no_results(self):
        response = self.client.get('/service/reviews/no_slug/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['object_list']), 0)
