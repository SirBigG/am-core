from http import HTTPStatus

from django.test import TestCase

from core.adverts.models import Advert, AdvertImage, get_advert_max_photos
from core.utils.tests.factories import UserFactory
from core.utils.tests.utils import make_image


def make_named_image(name):
    image = make_image()
    image.name = name
    return image


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
        response = self.client.post(
            "/adverts/create/", data={"title": "test", "description": "test", "price": 100, "contact": "test"}
        )
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, "/adverts/")
        # test that advert was created
        self.assertEqual(Advert.objects.count(), 1)
        self.assertEqual(AdvertImage.objects.count(), 0)

    def test_post_with_multiple_photos(self):
        response = self.client.post(
            "/adverts/create/",
            data={
                "title": "test",
                "description": "test",
                "price": 100,
                "photos": [make_named_image("first.jpg"), make_named_image("second.jpg")],
                "contact": "test",
            },
        )
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        advert = Advert.objects.get()
        self.assertEqual(advert.photos.count(), 2)

    def test_post_limits_photo_count(self):
        photos = [make_named_image(f"test-{index}.jpg") for index in range(get_advert_max_photos() + 1)]
        response = self.client.post(
            "/adverts/create/",
            data={"title": "test", "description": "test", "price": 100, "photos": photos, "contact": "test"},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertFormError(
            response.context["form"],
            "photos",
            f"Можна додати не більше {get_advert_max_photos()} фото. Зараз доступно: {get_advert_max_photos()}.",
        )
        self.assertEqual(Advert.objects.count(), 0)

    def test_authenticated_post(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.post(
            "/adverts/create/", data={"title": "test", "description": "test", "price": 100, "contact": "test"}
        )
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, "/adverts/")
        # test that advert was created
        self.assertEqual(Advert.objects.filter(user_id=user.pk).count(), 1)


class ProfileAdvertTests(TestCase):
    def test_profile_list_uses_adverts_template(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.get("/profile/adverts")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "adverts/profile/list.html")

    def test_profile_create_sets_logged_in_user(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.post(
            "/profile/adverts/create",
            data={
                "title": "test",
                "description": "test",
                "price": 100,
                "contact": "test",
            },
        )
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, "/profile/adverts")
        self.assertEqual(Advert.objects.filter(user=user).count(), 1)
