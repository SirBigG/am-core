#-*- coding: utf-8 -*-

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from django_any import any_model
from django_any.contrib.auth import any_user
from django_any.forms import any_form

from .models import UserInformation, Region
from .forms import UserRegistrationForm


client=Client()

class UserInformationTestCase(TestCase):
    def setUp(self):
        User.objects.create_user(username='bro', email='bro@example.com', password='787898')
        User.objects.create_user(username='chick', email='chick@example.com', password='foo')

    def test_UserInformation(self):
        ter = any_model(Region, region_field='Ternopil')
        kyi = any_model(Region, region_field='Kyiv')

        bro = User.objects.get(username='bro')
        chick = User.objects.get(username='chick')
        ter = Region.objects.get(pk=ter.pk)
        kyi = Region.objects.get(pk=kyi.pk)

        inf_bro = any_model(UserInformation,
                            profile=bro, birth_date=timezone.now(),
                            about='cool man', breed=u'армавір', location=ter)
        inf_bro.save()

        inf_chick = any_model(UserInformation,
                              profile=chick, birth_date=timezone.now(),
                              about='nice chick', breed=u'домінікан', location=kyi)
        inf_chick.save()

        self.assertEqual(inf_bro.location.region_field, 'Ternopil')
        self.assertEqual(inf_bro.profile.email, 'bro@example.com')
        self.assertEqual(bro.email, 'bro@example.com')
        self.assertEqual(inf_bro.breed, u'армавір')

        self.assertEqual(inf_chick.location.region_field, 'Kyiv')
        self.assertEqual(inf_chick.profile.email, 'chick@example.com')
        self.assertEqual(chick.email, 'chick@example.com')
        self.assertEqual(inf_chick.breed, u'домінікан')

class UserRegistrationFormTestCase(TestCase):
    def setUp(self):
        User.objects.create_user(username='admin', email='bro@example.com', password='787898')

    def test_form_validation(self):
        post, files = any_form(UserRegistrationForm)
        form = UserRegistrationForm(post,files)
        self.assertFalse(form.is_valid())
        self.assertRaisesMessage('password_mismatch',
                                 _("The two password fields didn't match."))

        form_data1={'username': 'Antoni',
                    'email': 'aa@aa.com','password1': '1234', 'password2': '1234'}
        form1 = UserRegistrationForm(data=form_data1)
        self.assertTrue(form1.is_valid())

        form_data2={'username':'admin',
                    'email':'ex@ex.ua','password1':'1234','password2':'1234'}
        form2=UserRegistrationForm(data=form_data2)
        self.assertFalse(form2.is_valid())
        self.assertRaisesMessage('username_exist',
                                 _("The username already exists. Please try another one."))

        form_data2={'username': 'user',
                    'email': 'bro@example.com','password1': '1234','password2': '1234'}
        form2=UserRegistrationForm(data=form_data2)
        self.assertFalse(form2.is_valid())
        self.assertRaisesMessage('email_exist',
                                 _("The email already exists. Please try another one."))

    def test_register_form_view(self):
        responce=client.get('/user/register/')
        self.assertEqual(responce.status_code, 200)
        form_data2={'username':'admin',
                    'email':'ex@ex.ua','password1':'1234','password2':'1234'}
        responce1 = client.post('/user/register/', data=form_data2)
        self.assertEqual(responce1.status_code,200)
        user = User.objects.get(username= 'admin')
        self.assertIsNotNone(user)
        self.assertEqual(user.is_authenticated(), True)

    def test_login_form_view(self):
        is_login = client.login(username='admin', password='787898')
        self.assertTrue(is_login)
        responce=client.get('/user/login/')
        self.assertEqual(responce.status_code, 200)
        user = User.objects.get(username= 'admin')
        self.assertEqual(user.is_authenticated(), True)

    def test_logout_view(self):
        is_login = client.login(username='admin', password='787898')
        self.assertTrue(is_login)
        is_logout = client.get('/user/logout/')
        self.assertEqual(is_logout.status_code, 301)
        user = User.objects.get(username= 'admin')
        self.assertEqual(user.is_authenticated(), False)
