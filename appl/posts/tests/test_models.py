# -*- coding: utf-8 -*-

from django.test import TestCase

from utils.tests.factories import PostFactory, PhotoFactory, CommentFactory, \
    CategoryFactory


class PostTests(TestCase):

    def setUp(self):
        self.post = PostFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.post), u'Заголовок')

    def test_get_absolute_url(self):
        parent = CategoryFactory(slug='aaa')
        child = CategoryFactory(parent=parent, slug='bbb')
        child2 = CategoryFactory(parent=child, slug='ccc')
        post = PostFactory(rubric=child2, slug='ddd', id='12')
        self.assertEqual(post.get_absolute_url(), '/bbb/ccc/ddd-12.html')


class PhotoTests(TestCase):

    def setUp(self):
        self.photo = PhotoFactory()

    def tearDown(self):
        import os
        os.remove('media/images/example.jpg')

    def test_str_representation(self):
        self.assertEqual(str(self.photo), str(self.photo.id))

    def test_resize(self):
        self.assertEqual(self.photo.image.width, 1000)
        self.assertEqual(self.photo.image.height, 666)


class CommentTests(TestCase):

    def setUp(self):
        self.comment = CommentFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.comment), 'John')
