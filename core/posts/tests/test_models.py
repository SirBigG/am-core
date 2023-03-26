import os

from django.test import TestCase
from django.conf import settings

from core.utils.tests.factories import PostFactory, PhotoFactory, CategoryFactory

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


class PhotoTests(TestCase):

    def setUp(self):
        self.photo = PhotoFactory()

    def tearDown(self):
        self.photo.delete()

    def test_str_representation(self):
        self.assertEqual(str(self.photo), str(self.photo.id))

    def test_resize(self):
        self.assertEqual(self.photo.image.width, 1000)
        self.assertEqual(self.photo.image.height, 667)

    def test_thumbnail(self):
        thumbnail = self.photo.thumbnail(400, 300)
        self.assertEqual(thumbnail,
                         '%s%s' % (settings.MEDIA_URL, 'images/thumb/400/%s' % self.photo.image.name.split('/')[-1]))
        os.remove(settings.MEDIA_ROOT + '/images/thumb/400/%s' % self.photo.image.name.split('/')[-1])

    def test_no_file_thumbnail(self):
        photo = PhotoFactory()
        photo.image = 'images/test_no_file.jpg'
        self.assertIsNone(photo.thumbnail())


class PhotoDeleteTest(TestCase):
    def test_file_after_object_delete(self):
        photo = PhotoFactory()
        path = photo.image.path
        photo.delete()
        import os
        with self.assertRaises(FileNotFoundError):
            os.remove(path)
