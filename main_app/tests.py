from django.test import TestCase
from datetime import datetime

from .models import UserInformation, User, Announcement, Region
# Create your tests here.

class UserInformationTestCase(TestCase):
    def setUp(self):
        User.objects.create_user(username='bro', email='bro@example.com', password='787898')
        User.objects.create_user(username='chick', email='chick@example.com', password='foo')
        Region.objects.create(region_field='Ternopil')
        Region.objects.create(region_field='Kyiv')


    def test_user_information(self):
        bro = User.objects.get(username= 'bro')
        chick = User.objects.get(username='chick')
        ter = Region.objects.get(id=1)
        kyi = Region.objects.get(id=2)

        inf_bro = UserInformation(profile=bro, birth_date= datetime.now(),  about = 'cool man')
        inf_bro.save()
        inf_bro.location.add(ter)

        inf_chick = UserInformation(profile=chick, birth_date = datetime.now(), about = 'nice chick')
        inf_chick.save()
        inf_chick.location.add(kyi)

        self.assertEqual(inf_bro.location.get().region_field, 'Ternopil')
        self.assertEqual(inf_bro.profile.email, 'bro@example.com')
        self.assertEqual(bro.email , 'bro@example.com')

        self.assertEqual(inf_chick.location.get().region_field, 'Kyiv')
        self.assertEqual(inf_chick.profile.email, 'chick@example.com')
        self.assertEqual(chick.email , 'chick@example.com')