# -*- coding: utf-8 -*-

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
        response = client.post('/login/', data={'username': 'agrokent9@test.com',
                                                'password': '12345'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
        response = client.get('/login/')
        context_data = response.context_data
        self.assertEqual(response.status_code, 200)
        # TODO: need check render template
        # self.assertTemplateUsed(response, 'pro_auth/login.html')
        self.assertTrue(context_data['view'].request.user.is_authenticated())
        self.assertTrue(isinstance(context_data['form'], AuthenticationForm))

    def test_logout(self):
        client.login(username=self.user.email, password='12345')
        response = client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context_data['view'].request.user.is_authenticated())
        response = client.get('/logout/')
        self.assertEqual(response.status_code, 302)
        response = client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context_data['view'].request.user.is_authenticated())

    def test_register(self):
        # Get request
        response = client.get('/register/')
        self.assertEqual(response.status_code, 200)
        # TODO: need check render template
        # self.assertTemplateUsed(response, 'pro_auth/register.html')
        self.assertTrue(isinstance(response.context_data['form'], UserCreationForm))
        # Post request
        location = LocationFactory()
        data = {'email': 'test@test.com',
                'password1': '11111',
                'password2': '11111',
                'phone1': '+380991234567',
                'location': location.pk,
                }
        response = client.post('/register/', data=data)
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='test@test.com')
        self.assertTrue(user.is_authenticated())
