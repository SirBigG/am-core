# -*- coding: utf-8 -*-

from django.test import TestCase

from utils.tests.factories import LocationFactory  # UserFactory

from appl.pro_auth.forms import UserCreationForm  # UserAdminChangeForm
from appl.pro_auth.models import User

from django.forms import ValidationError
# from django.contrib.auth.hashers import make_password


class UserCreationFormTests(TestCase):

    def test_form_valid(self):
        location = LocationFactory()
        data = {'email': 'test@test.com',
                'password1': '11111',
                'password2': '11111',
                'phone1': '+380991234567',
                'location': location.pk,
                }
        form = UserCreationForm(data=data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_phone(self):
        location = LocationFactory()
        data = {'email': 'test@test.com',
                'password1': '11111',
                'password2': '11111',
                'phone1': '0991234567',
                'location': location.pk,
                }
        form = UserCreationForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {'phone1': [u'Enter a valid phone number.']})

    def test_clean_password2(self):
        form = UserCreationForm(data={'password1': '12345',
                                      'password2': '12345'})
        form.is_valid()
        self.assertEqual(form.clean_password2(), '12345')
        form1 = UserCreationForm(data={'password1': '12345',
                                       'password2': '123'})
        form1.is_valid()
        self.assertRaisesMessage(form1.clean_password2(),
                                 "The two password fields didn't match.")
        self.assertRaises(ValidationError, form1.clean_password2())


class UserAdminChangeFormTest(TestCase):

    def test_form_validation(self):
        pass
        # password = make_password('12345')
        # user = UserFactory(password=password)
        # form = UserAdminChangeForm(data=user.__dict__, instance=user)
        # import pdb; pdb.set_trace();
        # TODO: need to work
        # self.assertTrue(form.is_valid())
