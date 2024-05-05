from django.test import TestCase

from core.posts.templatetags.post_extras import full_url, group_by, grouped, main_menu, second_menu, times
from core.utils.tests.factories import CategoryFactory


class PostExtrasTests(TestCase):
    def test_main_menu(self):
        CategoryFactory.create_batch(size=5)
        self.assertEqual(len(main_menu()["roots"]), 5)

    def test_full_url(self):
        url = "/foo/asd.html"
        self.assertEqual(full_url(url), "localhost:8000/foo/asd.html")

    def test_grouped(self):
        items = [1, 2, 3, 4]
        group = grouped(items, 2)
        self.assertEqual(next(group), [1, 2])
        self.assertEqual(next(group), [3, 4])

    def test_group_by_filter(self):
        value = [1, 2, 3]
        groups = group_by(value, 2)
        i = 0
        for _ in groups:
            i += 1
        self.assertEqual(i, 2)
        groups = group_by(value, 3)
        for _ in groups:
            i += 1
        self.assertEqual(i, 3)

    def test_times_filter(self):
        self.assertEqual(times(5), range(1, 6))

    def test_second_menu(self):
        parent = CategoryFactory(slug="parent")
        CategoryFactory(parent=parent)
        CategoryFactory(parent=parent)
        self.assertEqual(len(second_menu("parent")["menu_items"]), 2)
