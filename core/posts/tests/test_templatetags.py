from django.test import TestCase, override_settings
from django.conf import settings

from core.utils.tests.factories import CategoryFactory

from core.posts.templatetags.post_extras import main_menu, full_url, group_by, grouped, times, second_menu, \
    static_version, index_categories, get_domain


class PostExtrasTests(TestCase):

    def test_main_menu(self):
        CategoryFactory.create_batch(size=5)
        self.assertEqual(len(main_menu()['roots']), 5)

    def test_index_categories(self):
        CategoryFactory.create_batch(size=5)
        self.assertEqual(len(index_categories()['roots']), 5)

    def test_full_url(self):
        url = '/foo/asd.html'
        self.assertEqual(full_url(url), 'localhost:8000/foo/asd.html')

    def test_grouped(self):
        l = [1, 2, 3, 4]
        group = grouped(l, 2)
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
        parent = CategoryFactory(slug='parent')
        CategoryFactory(parent=parent)
        CategoryFactory(parent=parent)
        self.assertEqual(len(second_menu('parent')['menu_items']), 2)

    def test_static_version_without_settings(self):
        self.assertEqual(static_version('path/to/file.css'), '%spath/to/file.css' % settings.STATIC_URL)

    @override_settings(MEDIA_VERSION='1.0')
    def test_static_version_with_setting(self):
        self.assertEqual(static_version('path/to/file.css'), '%spath/to/file.css?1.0' % settings.STATIC_URL)

    def test_get_domain(self):
        self.assertEqual("http://test.com/test", "test.com")
