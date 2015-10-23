#-*- coding: utf-8 -*-

from django.test import TestCase
from django.utils import timezone


from .models import User, Announcement, Region, Category, Post
# Create your tests here.


class PostTestCase(TestCase):
    def setUp(self):
        Category.objects.create(category_field='Post pigeons')
        Post.objects.create(title=u'породи', date=timezone.now(), text=u'текст про породи')

    def test_post(self):
        cat = Category.objects.get(id=1)
        post = Post.objects.get(id = 1)
        post.post_category=cat

        self.assertEqual(post.title, u'породи')
        self.assertEqual(post.text, u'текст про породи')
        self.assertEqual(post.post_category.category_field, 'Post pigeons')


class AnnouncementTestCase(TestCase):
    def setUp(self):
        User.objects.create_user(username='user', email='ta@ta.com', password='787898')
        Announcement.objects.create(
            author=User.objects.get(username='user'), title='sale pigeons',
            date=timezone.now(),text='announcement text'
        )

    def test_announcement(self):
        user = User.objects.get(username='user')
        ann = Announcement.objects.get(author=user)

        self.assertEqual(ann.author.username, 'user')
        self.assertEqual(ann.author.email, 'ta@ta.com')
        self.assertEqual(ann.title, 'sale pigeons')
        self.assertEqual(ann.text, 'announcement text')
