import os
from http import HTTPStatus

from django.test import TestCase, override_settings
from PIL import Image

from core.adverts.models import Advert, AdvertImage, get_advert_max_photos
from core.utils.tests.factories import UserFactory
from core.utils.tests.utils import make_image


def make_named_image(name):
    image = make_image()
    image.name = name
    return image


def assert_safe_advert_image_name(test_case, image_name):
    basename = os.path.basename(image_name)

    test_case.assertRegex(basename, r"^advert-[0-9a-f]{32}\.jpg$")
    test_case.assertEqual(image_name, f"adverts/images/{basename}")


class TestAdvertFormView(TestCase):
    def test_not_authenticated_form(self):
        response = self.client.get("/adverts/create/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "adverts/form.html")
        self.assertContains(response, 'name="photos"', count=get_advert_max_photos())
        self.assertContains(response, "multiple")
        self.assertContains(response, 'class="visually-hidden advert-photo-input"')
        self.assertContains(response, 'class="advert-photo-slot-button"', count=get_advert_max_photos())
        self.assertContains(response, 'for="id_photos"')
        self.assertContains(response, 'class="advert-photo-slot-text">Додати', count=get_advert_max_photos())
        self.assertContains(response, "site-login-prompt")
        self.assertContains(response, "/login/?next=/adverts/create/")

    def test_authenticated(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.get("/adverts/create/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "adverts/form.html")
        self.assertNotContains(response, "Маєте акаунт?")

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

    def test_main_image_uses_safe_unique_name_after_upload(self):
        advert = Advert.objects.create(
            title="test",
            description="test",
            price=100,
            contact="test",
            image=make_named_image("Привіт bad name <script>.png"),
        )

        assert_safe_advert_image_name(self, advert.image.name)
        self.assertNotIn("Привіт", advert.image.name)
        with Image.open(advert.image.path) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertGreater(image.size[0], 0)

    def test_extra_photo_uses_safe_unique_name_after_upload(self):
        advert = Advert.objects.create(title="test", description="test", price=100, contact="test")
        photo = AdvertImage.objects.create(advert=advert, image=make_named_image("Привіт bad name <script>.png"))

        assert_safe_advert_image_name(self, photo.image.name)
        self.assertNotIn("Привіт", photo.image.name)
        with Image.open(photo.image.path) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertGreater(image.size[0], 0)

    @override_settings(ADVERT_IMAGE_WIDTH=1200)
    def test_large_photo_is_prepared_for_detail_gallery(self):
        advert = Advert.objects.create(
            title="large",
            description="test",
            price=100,
            contact="test",
            image=make_image({"width": 1600, "height": 1000}),
        )

        with Image.open(advert.image.path) as image:
            self.assertEqual(image.size, (1200, 750))

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

    def test_list_does_not_show_no_photo_placeholder(self):
        Advert.objects.create(title="test", description="test", price=100, contact="test")
        response = self.client.get("/adverts/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "test")
        self.assertNotContains(response, "Без фото")

    def test_homepage_handles_advert_without_photo(self):
        Advert.objects.create(title="test", description="test", price=100, contact="test")
        response = self.client.get("/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "test")

    @override_settings(USE_IMGPROXY=False)
    def test_list_uses_original_advert_image_when_imgproxy_disabled(self):
        Advert.objects.create(
            title="test",
            description="test",
            price=100,
            contact="test",
            image=make_named_image("test.jpg"),
        )

        response = self.client.get("/adverts/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, 'src="/media/adverts/images/')
        self.assertNotContains(response, "/imgproxy/")

    @override_settings(
        USE_IMGPROXY=True,
        IMGPROXY_KEY="0000000000000000000000000000000000000000000000000000000000000000",
        IMGPROXY_SALT="0000000000000000000000000000000000000000000000000000000000000000",
        IMGPROXY_BASE_URL="/imgproxy",
    )
    def test_list_uses_imgproxy_for_advert_image_when_enabled(self):
        Advert.objects.create(
            title="test",
            description="test",
            price=100,
            contact="test",
            image=make_named_image("test.jpg"),
        )

        response = self.client.get("/adverts/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, 'src="/imgproxy/')

    @override_settings(USE_IMGPROXY=False)
    def test_detail_renders_grouped_gallery_without_raw_image_navigation(self):
        advert = Advert.objects.create(
            title="test",
            description="<p>description</p>",
            price=100,
            contact="test",
            image=make_named_image("test.jpg"),
        )
        AdvertImage.objects.create(advert=advert, image=make_named_image("extra.jpg"))

        response = self.client.get(advert.get_absolute_url())

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, 'class="advert-detail__main-photo js-smartPhoto"')
        self.assertContains(response, f'data-advert-gallery-main="{advert.id}"')
        self.assertContains(response, 'class="advert-detail__lightbox-items" aria-hidden="true" hidden')
        self.assertContains(response, f'data-group="advert-{advert.id}"', count=2)
        self.assertNotContains(response, "2 фото")
        self.assertNotContains(response, 'class="advert-detail__thumb js-smartPhoto"')
        self.assertNotContains(response, 'target="_blank" rel="noopener"')

    def test_photo_urls_keep_legacy_main_image_before_extra_photos(self):
        advert = Advert.objects.create(
            title="test",
            description="test",
            price=100,
            contact="test",
            image=make_named_image("legacy.jpg"),
        )
        extra = AdvertImage.objects.create(advert=advert, image=make_named_image("extra.jpg"))

        self.assertEqual(advert.primary_image_url, advert.image.url)
        self.assertEqual(advert.photo_urls, [advert.image.url, extra.image.url])


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

    def test_profile_advert_update_date_requires_post(self):
        user = UserFactory()
        advert = Advert.objects.create(user=user, title="test", description="test", price=100, contact="test")
        self.client.force_login(user)

        response = self.client.get(f"/profile/adverts/{advert.pk}/update-date/")

        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)

    def test_profile_advert_update_date_post_updates_advert(self):
        user = UserFactory()
        advert = Advert.objects.create(user=user, title="test", description="test", price=100, contact="test")
        original_updated = advert.updated
        self.client.force_login(user)

        response = self.client.post(f"/profile/adverts/{advert.pk}/update-date/")

        advert.refresh_from_db()
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, "/profile/adverts")
        self.assertGreater(advert.updated, original_updated)

    def test_profile_advert_delete_requires_post(self):
        user = UserFactory()
        advert = Advert.objects.create(user=user, title="test", description="test", price=100, contact="test")
        self.client.force_login(user)

        response = self.client.get(f"/profile/adverts/{advert.pk}/delete/")

        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)
        self.assertTrue(Advert.objects.filter(pk=advert.pk).exists())

    def test_profile_advert_delete_post_removes_advert(self):
        user = UserFactory()
        advert = Advert.objects.create(user=user, title="test", description="test", price=100, contact="test")
        self.client.force_login(user)

        response = self.client.post(f"/profile/adverts/{advert.pk}/delete/")

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, "/profile/adverts")
        self.assertFalse(Advert.objects.filter(pk=advert.pk).exists())

    def test_profile_advert_deactivate_requires_post(self):
        user = UserFactory()
        advert = Advert.objects.create(user=user, title="test", description="test", price=100, contact="test")
        self.client.force_login(user)

        response = self.client.get(f"/profile/adverts/{advert.pk}/deactivate/")

        advert.refresh_from_db()
        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)
        self.assertTrue(advert.is_active)

    def test_profile_advert_deactivate_post_deactivates_advert(self):
        user = UserFactory()
        advert = Advert.objects.create(user=user, title="test", description="test", price=100, contact="test")
        self.client.force_login(user)

        response = self.client.post(f"/profile/adverts/{advert.pk}/deactivate/")

        advert.refresh_from_db()
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, "/profile/adverts")
        self.assertFalse(advert.is_active)

    @override_settings(USE_IMGPROXY=False)
    def test_profile_update_uses_original_advert_image_when_imgproxy_disabled(self):
        user = UserFactory()
        advert = Advert.objects.create(
            user=user,
            title="test",
            description="test",
            price=100,
            contact="test",
            image=make_named_image("test.jpg"),
        )
        self.client.force_login(user)

        response = self.client.get(f"/profile/adverts/update/{advert.pk}")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, 'src="/media/adverts/images/')
        self.assertContains(response, "advert-existing-photo")
        self.assertContains(response, "Вже додано 1 фото. Можна додати ще 4.")
        self.assertContains(response, 'name="photos"', count=get_advert_max_photos() - 1)
        self.assertNotContains(response, "/imgproxy/")
        self.assertNotContains(response, 'target="_blank" rel="noopener"')
