from __future__ import unicode_literals

import os

from django.test import TestCase, Client
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.conf import settings
from django.urls import reverse

from core.utils.tests.factories import UserFactory, LocationFactory
from core.utils.tests.utils import HtmlTestCaseMixin

from core.pro_auth.forms import EmailConfirmForm
from core.pro_auth.models import User


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
        self.assertTrue(context_data['view'].request.user.is_authenticated())
        self.assertTrue(isinstance(context_data['form'], AuthenticationForm))

    def test_login_ajax(self):
        response = client.post('/login/', data={'username': self.user.email,
                                                'password': '12345'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user'], self.user.pk)
        self.assertEqual(response.json()['status'], 'ok')
        response = client.get('/login/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        context_data = response.context_data
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pro_auth/login_form.html')
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
        response = client.get('/register/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pro_auth/register.html')
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
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['location'], '/')
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


class PersonalIndexViewTests(HtmlTestCaseMixin, TestCase):
    def test_response_ok(self):
        user = UserFactory()
        client.login(username=user.email, password='12345')
        response = client.get('/user/%d/' % user.pk)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'personal/personal_index.html')
        response = client.get('/user/%d/update/' % user.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIdIn('root', response.content)

    def test_user_not_login(self):
        response = client.get('/user/2353647/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['location'], settings.LOGIN_URL + '?next=/user/2353647/')


class UserPasswordResetTests(TestCase):
    def test_get_confirm(self):
        response = self.client.get('/password/confirm/email/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pro_auth/email_confirm_for_pass.html')
        self.assertTrue(isinstance(response.context['form'], EmailConfirmForm))

    def test_post_confirm(self):
        UserFactory(email='test@test.com')
        response = self.client.post('/password/confirm/email/', data={'email': 'test@test.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        self.assertTrue(User.objects.get(email='test@test.com').validation_key)

    def test_get_check(self):
        UserFactory(email='test@test.com', validation_key='hashing')
        response = self.client.get('/password/check/email/hashing.html')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.context['form'], SetPasswordForm))
        self.assertTemplateUsed(response, 'pro_auth/check_password.html')
        # Test bad hash
        response = self.client.get('/password/check/email/hashingssss.html')
        self.assertEqual(response.status_code, 404)

    def test_post_check(self):
        UserFactory(email='test@test.com', validation_key='hash')
        response = self.client.post('/password/check/email/hash.html', {'new_password1': '11111',
                                                                        'new_password2': '11111'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['location'], '/')
        user = User.objects.get(email='test@test.com')
        self.assertFalse(user.validation_key)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)


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


class SocialRegisterViewTests(TestCase):
    def test_valid_data(self):
        loc = LocationFactory()
        data = {'email': 'test@test.com', 'phone1': '+380991234567', 'password1': '11111', 'password2': '11111',
                'location': loc.pk}
        response = self.client.post('/register/social/vk-oauth2/', data=data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['location'], reverse('social:complete', args=('vk-oauth2',)))
        session = self.client.session
        self.assertIsNotNone(session.get('social_form_data'))

    def test_get(self):
        response = self.client.post('/register/social/vk-oauth2/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pro_auth/register_social.html')


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
