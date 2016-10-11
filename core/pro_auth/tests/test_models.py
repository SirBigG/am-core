from __future__ import unicode_literals

from django.test import TestCase

from core.utils.tests.factories import UserFactory

from core.pro_auth.models import User


class UserModelTests(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_user_creation(self):
        self.assertEqual(User.objects.count(), 1)

    def test_unique_email(self):
        self.assertRaisesMessage(UserFactory(email='avtokent1@test.com'),
                                 "A user with that email already exists.")

    def test_str_representation(self):
        self.assertEqual(str(self.user), 'John')
        self.user.first_name = ''
        self.user.save()
        self.assertEqual(str(self.user), self.user.email)

    def test_fields_exist(self):
        self.assertTrue(hasattr(self.user, 'phone1'))
        self.assertTrue(hasattr(self.user, 'phone2'))
        self.assertTrue(hasattr(self.user, 'phone3'))
        self.assertTrue(hasattr(self.user, 'location'))
        self.assertTrue(hasattr(self.user, 'birth_date'))
        self.assertTrue(hasattr(self.user, 'avatar'))
        self.assertTrue(hasattr(self.user, 'validation_key'))
        self.assertTrue(hasattr(self.user, 'choices_owner'))

    def test_get_full_name(self):
        self.assertEqual(self.user.get_full_name(), 'John Dou')

    def test_short_name(self):
        self.assertEqual(self.user.get_short_name(), 'John')

    def test_email_user(self):
        # TODO: Add test
        pass

    def test_get_absolute_url(self):
        self.assertEqual(self.user.get_absolute_url(), '/user/%s/' % self.user.pk)

    def test_backend(self):
        self.assertEqual(self.user.backend,
                         ['core.pro_auth.backends.AuthBackend'])


class UserManagerTests(TestCase):

    def test_create_user(self):
        User.objects.create_user('aaaa@test.com', '+380991234567',
                                 '11111')
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(User.objects.all()[0].is_staff)
        self.assertFalse(User.objects.all()[0].is_superuser)

    def test_create_superuser(self):
        User.objects.create_superuser('aaaa@test.com', '+380991234567',
                                      '11111')
        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(User.objects.all()[0].is_staff)
        self.assertTrue(User.objects.all()[0].is_superuser)

    def test_crete_user_raises(self):
        u = User.objects
        # Create user test.
        with self.assertRaisesMessage(ValueError, 'The given email must be set'):
            u.create_user(email='', phone1='+380991234567', password='11111')
        with self.assertRaisesMessage(ValueError, 'The given phone must be set'):
            u.create_user(email='test@test.com', phone1='', password='11111')
        # Create superuser test.
        with self.assertRaisesMessage(ValueError, 'Superuser must have is_staff=True.'):
            u.create_superuser(email='test@test.com', phone1='+380991234567',
                               password='11111', is_staff=False)
        with self.assertRaisesMessage(ValueError, 'Superuser must have is_superuser=True.'):
            u.create_superuser(email='test@test.com', phone1='+380991234567',
                               password='11111', is_superuser=False)
