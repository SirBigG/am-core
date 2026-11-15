from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import override_settings
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from core.classifier.models import Category, CategoryHub, CategoryHubSection, CategoryURLRedirect
from core.companies.models import Company, Product
from core.posts.models import Photo, Post
from core.utils.tests.factories import CategoryFactory, LocationFactory, MetaDataFactory, PostFactory, StaffUserFactory


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class CropSetupTests(APITestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = StaffUserFactory(is_superuser=True)
        self.authenticate(self.user)
        self.root = CategoryFactory(slug="plant-root")
        self.crop = CategoryFactory(parent=self.root, slug="crop-api")
        self.catalog = CategoryFactory(parent=self.crop, slug="crop-varieties")
        self.post = PostFactory(rubric=self.catalog, title="Example variety")
        self.post.get_absolute_url()

    def authenticate(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def staff(self, *permissions):
        user = StaffUserFactory()
        user.user_permissions.add(*Permission.objects.filter(codename__in=permissions))
        return user

    def upload(self, size=(1200, 500), format="PNG"):
        output = BytesIO()
        Image.new("RGBA", size, (12, 100, 20, 100)).save(output, format=format)
        return SimpleUploadedFile("image.png", output.getvalue(), content_type="image/png")

    def category_patch(self, data, category=None):
        return self.client.patch(f"/api/content/categories/{(category or self.crop).pk}/", data, format="json")

    def test_complete_crop_setup_and_sectioned_public_render(self):
        created = self.client.post(
            "/api/content/categories/",
            {
                "value": "New crop",
                "slug": "new-crop-api",
                "parent": self.root.pk,
                "is_active": False,
                "seo": {"title": "Crop SEO", "description": "Crop description", "h1": "Crop heading"},
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        crop_id = created.data["id"]
        self.assertEqual(created.data["url"], "/new-crop-api/")
        images = self.client.patch(
            f"/api/content/categories/{crop_id}/images/",
            {
                "hero_image": self.upload(),
                "image": self.upload(),
            },
            format="multipart",
        )
        self.assertEqual(images.status_code, 200, images.data)
        hub = self.client.post(
            "/api/content/hubs/",
            {
                "category": crop_id,
                "layout": "sectioned",
                "description": "An API crop introduction",
            },
            format="json",
        )
        self.assertEqual(hub.status_code, 201, hub.data)
        self.assertEqual(hub.data["layout"], "sectioned")
        section = self.client.post(
            "/api/content/hub-sections/",
            {
                "hub": hub.data["id"],
                "category": self.catalog.pk,
                "role": "varieties",
                "title": "Our varieties",
            },
            format="json",
        )
        self.assertEqual(section.status_code, 201, section.data)
        step = self.client.post(
            "/api/content/guide-sections/", {"category": crop_id, "title": "Planting"}, format="json"
        )
        self.assertEqual(step.status_code, 201, step.data)
        placement = self.client.post(
            "/api/content/guide-placements/",
            {
                "section": step.data["id"],
                "post": self.post.pk,
            },
            format="json",
        )
        self.assertEqual(placement.status_code, 201, placement.data)
        self.assertEqual(
            self.client.patch(
                f"/api/content/categories/{crop_id}/",
                {
                    "is_active": True,
                },
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/content/hubs/{hub.data["id"]}/',
                {
                    "is_active": True,
                },
                format="json",
            ).status_code,
            200,
        )
        page = self.client.get(created.data["url"])
        self.assertContains(page, "An API crop introduction")
        self.assertContains(page, "Planting")
        self.assertContains(page, urlsplit(images.data["hero_image"]).path)
        self.assertIn("hub_sections", page.context)
        self.assertEqual(
            self.client.patch(
                f'/api/content/hubs/{hub.data["id"]}/',
                {
                    "layout": "invalid",
                },
                format="json",
            ).status_code,
            400,
        )

    def test_taxonomy_discovery_includes_inactive_records_and_is_private(self):
        Category.objects.filter(pk=self.catalog.pk).update(is_active=False)
        response = self.client.get("/api/content/categories/", {"parent": self.crop.pk, "is_active": "false"})
        self.assertEqual([row["id"] for row in response.data["results"]], [self.catalog.pk])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.get("/api/content/categories/?parent=bad").status_code, 400)
        self.assertEqual(self.client.delete(f"/api/content/categories/{self.crop.pk}/").status_code, 405)

    def test_category_permissions_and_token_only_authentication(self):
        self.client.credentials()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/api/content/categories/").status_code, 401)
        reader = self.staff("view_category")
        self.authenticate(reader)
        self.assertEqual(self.client.get("/api/content/categories/").status_code, 200)
        self.assertEqual(self.category_patch({"value": "Denied"}).status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/content/categories/",
                {
                    "slug": "denied",
                    "value": "Denied",
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/content/categories/{self.crop.pk}/images/",
                {
                    "hero_image": self.upload(),
                },
                format="multipart",
            ).status_code,
            403,
        )

    def test_seo_is_partial_isolated_and_does_not_rewrite_urls_or_images(self):
        shared = MetaDataFactory()
        Category.objects.filter(pk=self.crop.pk).update(meta=shared)
        Post.objects.filter(pk=self.post.pk).update(meta=shared)
        original = Category.objects.values().get(pk=self.crop.pk)
        response = self.category_patch({"value": "Renamed crop", "seo": {"h1": "Updated heading"}})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["seo"]["title"], shared.title)
        self.crop.refresh_from_db()
        self.catalog.refresh_from_db()
        self.assertNotEqual(self.crop.meta_id, shared.pk)
        self.post.refresh_from_db()
        self.assertEqual(self.post.meta.h1, shared.h1)
        self.assertEqual(self.crop.absolute_url, original["absolute_url"])
        self.assertEqual(self.category_patch({"seo": None}).status_code, 200)
        self.crop.refresh_from_db()
        self.assertIsNone(self.crop.meta_id)
        self.assertEqual(self.category_patch({"seo": {"title": "a" * 256}}).status_code, 400)
        self.assertEqual(self.category_patch({"absolute_url": "/forged/"}).status_code, 400)

    def test_rename_and_move_updates_descendants_articles_and_redirects(self):
        old_post = self.post.absolute_url
        new_root = CategoryFactory(slug="another-root")
        response = self.category_patch({"parent": new_root.pk, "slug": "renamed-crop"})
        self.assertEqual(response.status_code, 200, response.data)
        self.crop.refresh_from_db()
        self.catalog.refresh_from_db()
        self.post.refresh_from_db()
        self.assertEqual(self.crop.parent_id, new_root.pk)
        self.assertEqual(self.catalog.absolute_url, "/renamed-crop/crop-varieties/")
        self.assertTrue(self.post.absolute_url.startswith("/renamed-crop/crop-varieties/"))
        self.assertRedirects(
            self.client.get("/crop-api/"), "/renamed-crop/", status_code=301, fetch_redirect_response=False
        )
        self.assertRedirects(
            self.client.get("/crop-api/crop-varieties/?page=2"),
            "/renamed-crop/crop-varieties/?page=2",
            status_code=301,
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get(old_post), self.post.absolute_url, status_code=301, fetch_redirect_response=False
        )
        # Renaming back removes the self-alias and keeps redirects to the current path.
        self.assertEqual(self.category_patch({"slug": "crop-api"}).status_code, 200)
        self.assertFalse(CategoryURLRedirect.objects.filter(old_path="/crop-api/").exists())
        self.assertRedirects(
            self.client.get("/renamed-crop/"), "/crop-api/", status_code=301, fetch_redirect_response=False
        )

    def test_moves_reject_cycles_depth_reserved_paths_and_broken_hub_references(self):
        for data in (
            {"parent": self.crop.pk},
            {"parent": self.catalog.pk},
            {"slug": "api"},
            {"slug": "forum"},
            {"slug": "bad/path"},
        ):
            with self.subTest(data=data):
                self.assertEqual(self.category_patch(data).status_code, 400)
        hub = CategoryHub.objects.create(category=self.crop)
        other = CategoryFactory(parent=self.root, slug="external-catalog")
        CategoryHubSection.objects.create(hub=hub, category=other, role="varieties")
        # Moving the owning crop under its own varieties source creates a recursive reference.
        self.assertEqual(self.category_patch({"parent": other.pk}).status_code, 400)
        self.crop.refresh_from_db()
        self.assertEqual(self.crop.parent_id, self.root.pk)
        self.assertFalse(CategoryURLRedirect.objects.exists())

    def test_old_paths_cannot_be_reused_by_another_category(self):
        self.assertEqual(self.category_patch({"slug": "renamed"}).status_code, 200)
        response = self.client.post(
            "/api/content/categories/",
            {
                "value": "Another",
                "slug": "crop-api",
                "parent": self.root.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Category.objects.filter(slug="crop-api").exists())

    def test_localized_redirects_preserve_language_and_do_not_expose_hidden_categories(self):
        self.assertEqual(self.category_patch({"slug": "renamed"}).status_code, 200)
        self.assertRedirects(
            self.client.get("/en/crop-api/?page=2"),
            "/en/renamed/?page=2",
            status_code=301,
            fetch_redirect_response=False,
        )
        self.assertEqual(self.category_patch({"is_active": False}).status_code, 200)
        self.assertEqual(self.client.get("/crop-api/").status_code, 404)

    def test_reserved_slugs_apply_to_localized_api_requests(self):
        response = self.client.patch(
            f"/en/api/content/categories/{self.crop.pk}/", {"slug": "companies"}, format="json"
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_h1_only_metadata_has_nonempty_defaults_and_repeated_patch_is_idempotent(self):
        response = self.category_patch({"seo": {"h1": "Only a heading"}})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["seo"]["title"], self.crop.value)
        self.crop.refresh_from_db()
        metadata_id = self.crop.meta_id
        self.assertEqual(self.category_patch({"seo": {"h1": "Only a heading"}}).status_code, 200)
        self.crop.refresh_from_db()
        self.assertEqual(self.crop.meta_id, metadata_id)

    def test_photo_audit_failure_removes_new_upload_and_rolls_back_record(self):
        with patch("api.v1.content.media.audit", side_effect=IntegrityError("Audit conflict")):
            response = self.client.post(
                "/api/content/photos/",
                {
                    "post": self.post.pk,
                    "image": self.upload(),
                },
                format="multipart",
            )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Photo.objects.exists())
        self.assertFalse([path for path in Path(self.directory.name).rglob("*") if path.is_file()])

    def test_language_slugs_and_oversized_uploads_are_rejected(self):
        self.assertEqual(self.category_patch({"slug": "en"}).status_code, 400)
        upload = SimpleUploadedFile("too-large.png", b"x" * (10 * 1024 * 1024 + 1), content_type="image/png")
        response = self.client.patch(
            f"/api/content/categories/{self.crop.pk}/images/",
            {
                "hero_image": upload,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_category_images_preserve_hero_dimensions_and_support_clear(self):
        url = f"/api/content/categories/{self.crop.pk}/images/"
        response = self.client.patch(url, {"hero_image": self.upload(), "image": self.upload()}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.crop.refresh_from_db()
        self.assertEqual((self.crop.hero_image.width, self.crop.hero_image.height), (1200, 500))
        self.assertEqual((self.crop.image.width, self.crop.image.height), (300, 200))
        original = self.crop.image.name
        self.assertEqual(self.category_patch({"value": "Updated label"}).status_code, 200)
        self.crop.refresh_from_db()
        self.assertEqual(self.crop.image.name, original)
        self.assertEqual(self.client.patch(url, {"hero_image": None}, format="json").status_code, 200)
        self.crop.refresh_from_db()
        self.assertFalse(self.crop.hero_image)
        self.assertEqual(self.crop.image.name, original)

    def test_invalid_uploads_and_audit_failure_leave_no_files_or_rows(self):
        url = f"/api/content/categories/{self.crop.pk}/images/"
        for upload in (
            SimpleUploadedFile("image.svg", b"<svg></svg>", content_type="image/svg+xml"),
            self.upload((2, 2), "GIF"),
            self.upload((12001, 1)),
        ):
            self.assertEqual(self.client.patch(url, {"hero_image": upload}, format="multipart").status_code, 400)
        with patch("api.v1.content.management.audit", side_effect=IntegrityError("Audit conflict")):
            # Patch the imported audit reference used by the serializer as well.
            with patch("api.v1.content.media.audit", side_effect=IntegrityError("Audit conflict")):
                self.assertEqual(
                    self.client.patch(url, {"hero_image": self.upload()}, format="multipart").status_code, 400
                )
        self.crop.refresh_from_db()
        self.assertFalse(self.crop.hero_image)
        self.assertFalse([path for path in Path(self.directory.name).rglob("*") if path.is_file()])

    def test_photo_upload_update_clear_scope_and_delete(self):
        created = self.client.post(
            "/api/content/photos/",
            {
                "post": self.post.pk,
                "image": self.upload(),
                "description": "Variety photo",
                "source": "Own photo",
            },
            format="multipart",
        )
        self.assertEqual(created.status_code, 201, created.data)
        photo = Photo.objects.get(pk=created.data["id"])
        self.assertEqual((photo.image.width, photo.image.height), (1000, 417))
        url = f"/api/content/photos/{photo.pk}/"
        original = photo.image.name
        self.assertEqual(self.client.patch(url, {"description": "Changed"}, format="json").status_code, 200)
        photo.refresh_from_db()
        self.assertEqual(photo.image.name, original)
        self.assertEqual(
            self.client.patch(url, {"post": PostFactory(rubric=self.catalog).pk}, format="json").status_code, 400
        )
        self.assertEqual(self.client.patch(url, {"image": None}, format="json").status_code, 400)
        listed = self.client.get("/api/content/photos/", {"post": self.post.pk})
        self.assertEqual(listed.data["count"], 1)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(Photo.objects.exists())
        self.assertGreaterEqual(LogEntry.objects.count(), 3)

    def test_own_article_photo_permissions_do_not_expose_other_articles(self):
        editor = self.staff("change_own_post", "view_photo", "add_photo", "change_photo", "delete_photo")
        own = PostFactory(publisher=editor, rubric=self.catalog)
        hidden = Photo.objects.create(post=self.post, image=self.upload())
        self.authenticate(editor)
        self.assertEqual(self.client.get(f"/api/content/photos/{hidden.pk}/").status_code, 404)
        denied = self.client.post(
            "/api/content/photos/", {"post": self.post.pk, "image": self.upload()}, format="multipart"
        )
        self.assertEqual(denied.status_code, 400, denied.data)
        allowed = self.client.post("/api/content/photos/", {"post": own.pk, "image": self.upload()}, format="multipart")
        self.assertEqual(allowed.status_code, 201, allowed.data)
        reader = self.staff("view_post", "add_photo")
        self.authenticate(reader)
        denied = self.client.post("/api/content/photos/", {"post": own.pk, "image": self.upload()}, format="multipart")
        self.assertEqual(denied.status_code, 403, denied.data)

    def test_taxonomy_audit_failure_rolls_back_seo_and_url_changes(self):
        before = Category.objects.values().get(pk=self.crop.pk)
        with patch("api.v1.content.taxonomy.audit", side_effect=IntegrityError("Audit conflict")):
            response = self.category_patch({"slug": "rolled-back", "seo": {"title": "New metadata"}})
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Category.objects.values().get(pk=self.crop.pk), before)
        self.assertFalse(CategoryURLRedirect.objects.exists())

    def test_manual_product_matching_preserves_prices_and_rejects_hidden_or_other_category(self):
        company = Company.objects.create(name="Seller", website="https://example.com", location=LocationFactory())
        product = Product.objects.create(company=company, category=self.catalog, name="Offer", price="10")
        original = Product.objects.values().get(pk=product.pk)
        url = f"/api/content/products/{product.pk}/match/"
        for post in (PostFactory(rubric=self.crop), PostFactory(rubric=self.catalog, status=False)):
            response = self.client.patch(url, {"post_id": post.pk}, format="json")
            self.assertEqual(response.status_code, 400, response.data)
        response = self.client.patch(url, {"post_id": self.post.pk}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertEqual(product.match_status, Product.MatchStatus.CONFIRMED)
        self.assertEqual(product.post_id, self.post.pk)
        self.assertEqual(product.price, original["price"])
        self.assertEqual(product.price_updated_at, original["price_updated_at"])
        self.assertEqual(self.client.patch(url, {"post_id": None}, format="json").status_code, 200)
        product.refresh_from_db()
        self.assertIsNone(product.post_id)
        self.assertEqual(product.match_status, Product.MatchStatus.CONFIRMED)
        self.assertEqual(self.client.patch(url, {"price": "999"}, format="json").status_code, 400)
        self.authenticate(self.staff("view_product", "view_post"))
        self.assertEqual(self.client.patch(url, {"post_id": self.post.pk}, format="json").status_code, 403)
