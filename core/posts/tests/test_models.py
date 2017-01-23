from __future__ import unicode_literals

from django.test import TestCase

from core.utils.tests.factories import PostFactory, PhotoFactory, CommentFactory, \
    CategoryFactory

from core.classifier.models import Category


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

    def test_auto_slug_create(self):
        post = PostFactory(title='Тест автоідентифікатор', slug=None)
        self.assertEqual(post.slug, 'test-avtoidentyfikator')

    def test_category_created(self):
        rubric = CategoryFactory(value='breeds', is_for_user=True, is_active=True)
        post = PostFactory(rubric=rubric, title='Породи голубів', slug=None)
        self.assertEqual(post.slug, 'porody-holubiv')
        self.assertTrue(Category.objects.get(slug=post.slug))


class PhotoTests(TestCase):

    def setUp(self):
        self.photo = PhotoFactory()

    def tearDown(self):
        self.photo.delete()

    def test_str_representation(self):
        self.assertEqual(str(self.photo), str(self.photo.id))

    def test_resize(self):
        self.assertEqual(self.photo.image.width, 1000)
        self.assertEqual(self.photo.image.height, 666)


class PhotoDeleteTest(TestCase):
    def test_file_after_object_delete(self):
        photo = PhotoFactory()
        path = photo.image.path
        photo.delete()
        import os
        with self.assertRaises(FileNotFoundError):
            os.remove(path)


class CommentTests(TestCase):

    def setUp(self):
        self.comment = CommentFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.comment), 'John')
