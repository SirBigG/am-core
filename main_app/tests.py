#-*- coding: utf-8 -*-

from django.test import TestCase
from django.utils import timezone


from .models import UserInformation, User, Announcement, Region, Category, Post
# Create your tests here.

class UserInformationTestCase(TestCase):
    def setUp(self):
        User.objects.create_user(username='bro', email='bro@example.com', password='787898')
        User.objects.create_user(username='chick', email='chick@example.com', password='foo')
        Region.objects.create(region_field='Ternopil')
        Region.objects.create(region_field='Kyiv')


    def test_UserInformation(self):
        bro = User.objects.get(username='bro')
        chick = User.objects.get(username='chick')
        ter = Region.objects.get(id=1)
        kyi = Region.objects.get(id=2)

        inf_bro = UserInformation(
            profile=bro, birth_date= timezone.now(),  about ='cool man', breed=u'армавір'
        )
        inf_bro.save()
        inf_bro.location.add(ter)

        inf_chick = UserInformation(
            profile=chick, birth_date=timezone.now(), about='nice chick', breed=u'домінікан'
        )
        inf_chick.save()
        inf_chick.location.add(kyi)

        self.assertEqual(inf_bro.location.get().region_field, 'Ternopil')
        self.assertEqual(inf_bro.profile.email, 'bro@example.com')
        self.assertEqual(bro.email, 'bro@example.com')
        self.assertEqual(inf_bro.breed, u'армавір')

        self.assertEqual(inf_chick.location.get().region_field, 'Kyiv')
        self.assertEqual(inf_chick.profile.email, 'chick@example.com')
        self.assertEqual(chick.email, 'chick@example.com')
        self.assertEqual(inf_chick.breed, u'домінікан')


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
