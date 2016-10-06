from django.test import TestCase

from appl.utils.tests.factories import FeedbackFactory, MetaDataFactory


class FeedbackModelTest(TestCase):

    def setUp(self):
        self.feedback = FeedbackFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.feedback), 'Feedback topic')


class MetaDataTests(TestCase):

    def setUp(self):
        self.meta = MetaDataFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.meta), 'title')
