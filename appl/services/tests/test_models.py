from django.test import TestCase

from utils.tests.factories import FeedbackFactory


class FeedbackModelTest(TestCase):

    def setUp(self):
        self.feedback = FeedbackFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.feedback), 'Feedback topic')
