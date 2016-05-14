from django.test import TestCase, Client

client = Client()


class FeedbackViewTests(TestCase):

    def test_get_response(self):
        response = client.get('/service/feedback/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'services/feedback.html')

    def test_post_success_response(self):
        response = client.post('/service/feedback/', {'title': 'feed title', 'email': 'test@test.com',
                                                      'text': 'feed text'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'services/success.html')
