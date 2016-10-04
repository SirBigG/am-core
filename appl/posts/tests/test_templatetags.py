from __future__ import unicode_literals

from django.test import TestCase

from appl.utils.tests.factories import PostFactory, CategoryFactory

from appl.posts.templatetags.post_extras import posts_list, main_menu, \
    full_url, group_by, grouped, times


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
        self.assertEqual(full_url(url), 'https://agromega.in.ua/foo/asd.html')

    def test_grouped(self):
        l = [1, 2, 3, 4]
        group = grouped(l, 2)
        self.assertEqual(next(group), [1, 2])
        self.assertEqual(next(group), [3, 4])

    def test_group_by_filter(self):
        value = [1, 2, 3]
        groups = group_by(value, 2)
        i = 0
        for group in groups:
            i += 1
        self.assertEqual(i, 2)
        groups = group_by(value, 3)
        for group in groups:
            i += 1
        self.assertEqual(i, 3)

    def test_times_filter(self):
        self.assertEqual(times(5), range(1, 6))
