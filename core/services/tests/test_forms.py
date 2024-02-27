from unittest.mock import patch

from django.test import TestCase

from core.services.forms import FeedbackForm


class FeedbackFormTests(TestCase):

    @patch("django_recaptcha.fields.client.submit")
    def test_form_valid(self, mock_submit):
        form = FeedbackForm({'title': 'feed title',
                             'email': 'test@test.com',
                             'text': 'feed text', "g-recaptcha-response": "PASSED"})
        self.assertTrue(form.is_valid())
        mock_submit.assert_called_once()

    def test_form_invalid(self):
        form = FeedbackForm({'email': 'test@test.com',
                             'text': 'feed text'})
        self.assertFalse(form.is_valid())
