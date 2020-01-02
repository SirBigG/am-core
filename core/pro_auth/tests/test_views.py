import os

from django.test import TestCase, Client
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
from django.urls import reverse

from core.utils.tests.factories import UserFactory, LocationFactory
from core.utils.tests.utils import HtmlTestCaseMixin


client = Client()


class AuthTests(TestCase):

    def setUp(self):
        self.user = UserFactory()

    def test_login(self):
        response = client.post('/login/', data={'username': self.user.email,
                                                'password': '12345'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['location'], '/')
        response = client.get('/login/')
        context_data = response.context_data
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pro_auth/login.html')
        self.assertTrue(context_data['view'].request.user.is_authenticated)
        self.assertTrue(isinstance(context_data['form'], AuthenticationForm))

    # def test_login_ajax(self):
    #     response = client.post('/login/', data={'username': self.user.email,
    #                                             'password': '12345'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    #     self.assertEqual(response.status_code, 200)
    #     self.assertEqual(response.json()['user'], self.user.pk)
    #     self.assertEqual(response.json()['status'], 'ok')
    #     response = client.get('/login/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    #     self.assertEqual(response.status_code, 200)
    #     context_data = response.context_data
    #     self.assertEqual(response.status_code, 200)
    #     self.assertTemplateUsed(response, 'pro_auth/login_form.html')
    #     self.assertTrue(context_data['view'].request.user.is_authenticated)
    #     self.assertTrue(isinstance(context_data['form'], AuthenticationForm))

    def test_logout(self):
        client.login(username=self.user.email, password='12345')
        response = client.get('/', {'user': self.user})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['request'].user.is_authenticated)
        response = client.get('/logout/')
        self.assertEqual(response.status_code, 302)
        response = client.get('/')
        self.assertEqual(response.status_code, 200)


class PersonalIndexViewTests(HtmlTestCaseMixin, TestCase):
    def test_response_ok(self):
        user = UserFactory()
        client.login(username=user.email, password='12345')
        response = client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'personal/personal_index.html')
        response = client.get('/profile/update/')
        self.assertEqual(response.status_code, 200)
        self.assertIdIn('root', response.content)

    def test_user_not_login(self):
        response = client.get('/profile/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['location'], settings.LOGIN_URL + '?next=/profile/')


class IsAuthenticateTests(TestCase):
    def test_404(self):
        response = self.client.get('/is-authenticate/')
        self.assertEqual(response.status_code, 404)

    def test_no_authenticate(self):
        response = self.client.get('/is-authenticate/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('is_authenticate'), 0)

    def test_authenticate(self):
        user = UserFactory()
        user.set_password('12345')
        user.save()
        self.client.login(username=user.email, password='12345')
        response = self.client.get('/is-authenticate/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('is_authenticate'), 1)


class SocialExistUserLoginViewTests(TestCase):
    def test_get(self):
        response = self.client.post('/register/social/vk-oauth2/login/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pro_auth/login.html')

    def test_valid_data(self):
        _user = UserFactory(email='test@test.com')
        _user.set_password('11111')
        _user.save()
        data = {'username': 'test@test.com', 'password': '11111'}
        response = self.client.post('/register/social/vk-oauth2/login/', data=data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['location'], reverse('social:complete', args=('vk-oauth2',)))
        session = self.client.session
        self.assertIsNotNone(session.get('user_pk'))
