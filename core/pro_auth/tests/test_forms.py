from django.test import TestCase

from core.utils.tests.factories import LocationFactory, UserFactory

from core.pro_auth.forms import UserCreationForm, AdminUserChangeForm, UserChangeForm, EmailConfirmForm, \
    AdminUserCreationForm
from core.pro_auth.models import User

from django.forms import ValidationError


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
        form.save(commit=False)
        self.assertEqual(User.objects.count(), 0)
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
        self.assertIn('phone1', form.errors)

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


class AdminUserChangeFormTest(TestCase):

    def test_valid_form(self):
        user = UserFactory()
        data = {'email': user.email, 'date_joined': user.date_joined,
                'location': user.location.pk, 'phone1': user.phone1}
        form = AdminUserChangeForm(data=data, instance=user)
        self.assertTrue(form.is_valid())


class UserChangeFormTest(TestCase):
    def test_valid_form(self):
        user = UserFactory(email='test@test.com')
        data = {'email': 'newtest@test.com', 'location': user.location.pk,
                'phone1': user.phone1}
        form = UserChangeForm(data=data, instance=user)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertTrue(User.objects.get(email='newtest@test.com'))


class EmailConfirmFormTests(TestCase):
    def test_invalid_form(self):
        form = EmailConfirmForm({'email': 'aa@test.com'})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['email'], [str(form.error_messages.get('not_user'))])

    def test_valid_form(self):
        u = UserFactory(email='aaa@test.com')
        form = EmailConfirmForm({'email': 'aaa@test.com'})
        self.assertTrue(form.is_valid())
        # Test get_user
        self.assertEqual(form.get_user(), u)


class AdminUserCreationFormTests(TestCase):
    def test_form_valid(self):
        location = LocationFactory()
        data = {'email': 'test@test.com',
                'password1': '11111',
                'password2': '11111',
                'phone1': '+380991234567',
                'location': location.pk
                }
        form = AdminUserCreationForm(data=data)
        self.assertTrue(form.is_valid())
        form.save(commit=False)
        self.assertEqual(User.objects.count(), 0)
        form.save()
        self.assertEqual(User.objects.count(), 1)
