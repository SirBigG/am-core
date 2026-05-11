import importlib
import os
from unittest.mock import patch

from django.test import SimpleTestCase


class LiveStorageSettingsTests(SimpleTestCase):
    def load_live_settings(self, env):
        with patch.dict(os.environ, env, clear=False):
            import settings.live as live_settings

            return importlib.reload(live_settings)

    def test_s3_endpoint_url_is_normalized_with_https_scheme(self):
        live_settings = self.load_live_settings({"AWS_S3_ENDPOINT_URL": "storage.example.com"})

        self.assertEqual(live_settings.AWS_S3_ENDPOINT_URL, "https://storage.example.com")
        self.assertEqual(live_settings.STATIC_URL, "https://storage.example.com/static/")
        self.assertEqual(live_settings.MEDIA_URL, "https://storage.example.com/media/")

    def test_s3_endpoint_url_keeps_existing_scheme(self):
        live_settings = self.load_live_settings({"AWS_S3_ENDPOINT_URL": "https://storage.example.com"})

        self.assertEqual(live_settings.AWS_S3_ENDPOINT_URL, "https://storage.example.com")

    def test_s3_storage_backends_use_separate_media_and_static_locations(self):
        live_settings = self.load_live_settings({"AWS_S3_ENDPOINT_URL": "storage.example.com"})

        self.assertEqual(
            live_settings.STORAGES["default"],
            {
                "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
                "OPTIONS": {"location": "media"},
            },
        )
        self.assertEqual(
            live_settings.STORAGES["staticfiles"],
            {
                "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
                "OPTIONS": {"location": "static"},
            },
        )
