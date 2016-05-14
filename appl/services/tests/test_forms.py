from django.test import TestCase

from appl.services.forms import FeedbackForm


class FeedbackFormTests(TestCase):

    def test_form_valid(self):
        form = FeedbackForm({'title': 'feed title',
                             'email': 'test@test.com',
                             'text': 'feed text'})
        self.assertTrue(form.is_valid())

    def test_form_invalid(self):
        form = FeedbackForm({'email': 'test@test.com',
                             'text': 'feed text'})
        self.assertFalse(form.is_valid())
