from http import HTTPStatus

from django.test import TestCase

from core.adverts.models import Advert
from core.utils.tests.factories import UserFactory
from core.utils.tests.utils import make_image


class TestAdvertFormView(TestCase):
    def test_not_authenticated_form(self):
        response = self.client.get("/adverts/create/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "adverts/form.html")

    def test_authenticated(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.get("/adverts/create/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "adverts/form.html")

    def test_not_authenticated_post(self):
        response = self.client.post("/adverts/create/", data={
            "title": "test",
            "description": "test",
            "price": 100,
            "image": make_image(),
            "contact": "test"
        })
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, "/adverts/")
        # test that advert was created
        self.assertEqual(Advert.objects.count(), 1)

    def test_authenticated_post(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.post("/adverts/create/", data={
            "title": "test",
            "description": "test",
            "price": 100,
            "image": make_image(),
            "contact": "test"
        })
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, "/adverts/")
        # test that advert was created
        self.assertEqual(Advert.objects.filter(user_id=user.pk).count(), 1)
