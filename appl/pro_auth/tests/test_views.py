from __future__ import unicode_literals

import os
import hashlib

from django.test import TestCase, Client
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings

from appl.utils.tests.factories import UserFactory, LocationFactory

from appl.pro_auth.forms import UserCreationForm
from appl.pro_auth.models import User

from rest_framework.test import APIClient, APITestCase

api_client = APIClient()

client = Client()


class AuthTests(TestCase):

    def setUp(self):
        self.user = UserFactory()

    def test_login(self):
        response = client.post('/login/', data={'username': self.user.email,
                                                'password': '12345'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user'], self.user.pk)
        self.assertEqual(response.json()['status'], 'ok')
        response = client.get('/login/')
        context_data = response.context_data
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pro_auth/login.html')
        self.assertTrue(context_data['view'].request.user.is_authenticated())
        self.assertTrue(isinstance(context_data['form'], AuthenticationForm))

    def test_logout(self):
        client.login(username=self.user.email, password='12345')
        response = client.get('/', {'user': self.user})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['request'].user.is_authenticated())
        response = client.get('/logout/')
        self.assertEqual(response.status_code, 302)
        response = client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_register(self):
        # Get request
        response = client.get('/register/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pro_auth/register.html')
        self.assertTrue(isinstance(response.context_data['form'], UserCreationForm))
        # Post request
        os.environ['RECAPTCHA_TESTING'] = 'True'
        location = LocationFactory()
        data = {'email': 'test@test.com',
                'password1': '11111',
                'password2': '11111',
                'phone1': '+380991234567',
                'location': location.pk,
                'g-recaptcha-response': 'PASSED'
                }
        response = client.post('/register/', data=data)
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email='test@test.com')
        self.assertFalse(user.is_active)
        key = hashlib.sha256(str('new_user_%s_%s' % (user.email, user.phone1)).encode('utf-8')).hexdigest()
        self.assertEqual(user.validation_key, key)
        self.assertEqual(response.content, b'ok')
        del os.environ['RECAPTCHA_TESTING']


class UserEmailConfirmTests(TestCase):
    def setUp(self):
        self.user = UserFactory(is_active=False, validation_key='hash')

    def test_with_hash(self):
        response = client.get('/confirm/email/hash.html')
        self.assertEqual(response.status_code, 302)
        user = User.objects.all()[0]
        self.assertTrue(user.is_active)
        self.assertFalse(user.validation_key)
        self.assertEqual(response['location'], '/')
        response = client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_without_hash(self):
        response = client.get('/confirm/email/')
        self.assertEqual(response.status_code, 404)

    def test_bad_hash(self):
        response = client.get('/confirm/email/bad_hash.html')
        self.assertEqual(response.status_code, 404)


class UserViewSetTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.user.set_password('12345')
        self.user.save()
        api_client.login(email=self.user.email, password='12345')

    def test_put_response_ok(self):
        response = api_client.put('/users/%s/' % self.user.pk, data={'phone1': self.user.phone1,
                                                                     'email': self.user.email,
                                                                     'location': self.user.location.pk})
        self.assertEqual(response.status_code, 200)

    def test_response_with_error(self):
        response = api_client.put('/users/%s/' % self.user.pk, data={'phone1': self.user.phone1,
                                                                     'email': '',
                                                                     'location': self.user.location.pk})

        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data)
        self.assertNotIn('phone1', response.data)

    def test_response_ok(self):
        response = api_client.get('/users/%s/' % self.user.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.data)
        self.assertEqual(response.data['email'], self.user.email)
        self.assertEqual(response.data['location'], {'pk': self.user.location.pk,
                                                     'value': str(self.user.location)})

    def test_response_not_found(self):
        response = api_client.get('/users/11111/')
        self.assertEqual(response.status_code, 404)

    def test_personal_permission(self):
        user = UserFactory()
        # Test get
        response = api_client.get('/users/%s/' % user.pk)
        self.assertEqual(response.status_code, 403)
        # Test put
        response = api_client.put('/users/%s/' % user.pk, data={'phone1': user.phone1,
                                                                'email': user.email,
                                                                'location': user.location.pk})

        self.assertEqual(response.status_code, 403)


class PersonalIndexViewTests(TestCase):
    def test_response_ok(self):
        user = UserFactory()
        client.login(username=user.email, password='12345')
        response = client.get('/user/%d/' % user.pk)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'personal/personal_index.html')
        response = client.get('/user/%d/update/' % user.pk)
        self.assertEqual(response.status_code, 200)

    def test_user_not_login(self):
        response = client.get('/user/2353647/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['location'], settings.LOGIN_URL + '?next=/user/2353647/')
