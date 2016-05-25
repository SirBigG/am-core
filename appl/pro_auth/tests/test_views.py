# -*- coding: utf-8 -*-
import os
import hashlib

from django.test import TestCase, Client
from django.contrib.auth.forms import AuthenticationForm

from utils.tests.factories import UserFactory, LocationFactory

from appl.pro_auth.forms import UserCreationForm
from appl.pro_auth.models import User


client = Client()


class AuthTests(TestCase):

    def setUp(self):
        self.user = UserFactory()

    def test_login(self):
        response = client.post('/login/', data={'username': self.user.email,
                                                'password': '12345'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')
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
