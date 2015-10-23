#-*- coding: utf-8 -*-

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from apps.main_app.models import Region

from .models import UserInformation
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
            profile=bro, birth_date= timezone.now(),  about ='cool man', breed=u'армавір',
            phone='0991787345', location=ter
        )
        inf_bro.save()

        inf_chick = UserInformation(
            profile=chick, birth_date=timezone.now(), about='nice chick', breed=u'домінікан',
            phone='0991223456', location=kyi
        )
        inf_chick.save()

        self.assertEqual(inf_bro.location.region_field, 'Ternopil')
        self.assertEqual(inf_bro.profile.email, 'bro@example.com')
        self.assertEqual(bro.email, 'bro@example.com')
        self.assertEqual(inf_bro.breed, u'армавір')

        self.assertEqual(inf_chick.location.region_field, 'Kyiv')
        self.assertEqual(inf_chick.profile.email, 'chick@example.com')
        self.assertEqual(chick.email, 'chick@example.com')
        self.assertEqual(inf_chick.breed, u'домінікан')