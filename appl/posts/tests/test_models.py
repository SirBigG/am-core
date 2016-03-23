# -*- coding: utf-8 -*-

from django.test import TestCase

from utils.tests.factories import PostFactory, PhotoFactory, CommentFactory


class PostTests(TestCase):

    def setUp(self):
        self.post = PostFactory()

    def test_str_representation(self):
        self.assertEqual(unicode(self.post), u'Заголовок')


class PhotoTests(TestCase):

    def setUp(self):
        self.photo = PhotoFactory()

    def tearDown(self):
        import os
        os.remove('uploads/example.jpg')

    def test_str_representation(self):
        self.assertEqual(unicode(self.photo), unicode(self.photo.id))

    def test_resize(self):
        self.assertEqual(self.photo.image.width, 1000)
        self.assertEqual(self.photo.image.height, 666)


class CommentTests(TestCase):

    def setUp(self):
        self.comment = CommentFactory()

    def test_str_representation(self):
        self.assertEqual(unicode(self.comment), 'John')
