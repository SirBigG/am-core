# -*- coding: utf-8 -*-

from django.test import TestCase

from utils.tests.factories import PostFactory, CategoryFactory

from appl.posts.templatetags.post_extras import posts_list, main_menu, \
    full_url


class PostExtrasTests(TestCase):

    def test_posts_list(self):
        PostFactory.create_batch(size=11)
        self.assertEqual(len(posts_list(10)['posts']), 10)
        self.assertEqual(len(posts_list(5)['posts']), 5)

    def test_main_menu(self):
        CategoryFactory.create_batch(size=5)
        self.assertEqual(len(main_menu()['roots']), 5)

    def test_full_url(self):
        url = '/foo/asd.html'
        self.assertEqual(full_url(url), 'http://agromega.in.ua/foo/asd.html')
