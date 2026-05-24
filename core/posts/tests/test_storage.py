import os
import tempfile

from django.test import TestCase, override_settings
from PIL import Image

from core.utils.tests.factories import PhotoFactory


class PhotoStorageTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media_dir.name, MEDIA_URL="/media/")
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.media_dir.cleanup()

    def test_photo_upload_is_resized_and_converted_to_webp(self):
        photo = PhotoFactory()

        self.assertTrue(photo.image.name.endswith(".webp"))
        self.assertTrue(os.path.exists(photo.image.path))
        with Image.open(photo.image.path) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertLessEqual(image.width, 1000)
            self.assertLessEqual(image.height, 800)

    def test_thumbnail_creates_resized_media_file(self):
        photo = PhotoFactory()

        thumbnail_url = photo.thumbnail(320, 240)
        thumbnail_path = os.path.join(
            self.media_dir.name,
            "images",
            "thumb",
            "320",
            os.path.basename(photo.image.name),
        )

        self.assertEqual(thumbnail_url, f"/media/images/thumb/320/{os.path.basename(photo.image.name)}")
        self.assertTrue(os.path.exists(thumbnail_path))
        with Image.open(thumbnail_path) as image:
            self.assertLessEqual(image.width, 320)
            self.assertLessEqual(image.height, 240)

    def test_photo_delete_removes_uploaded_file(self):
        photo = PhotoFactory()
        image_path = photo.image.path

        photo.delete()

        self.assertFalse(os.path.exists(image_path))
