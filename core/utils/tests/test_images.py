from django.test import SimpleTestCase, override_settings

from core.utils.images import imgproxy_url


class ImageUrlTests(SimpleTestCase):
    @override_settings(USE_IMGPROXY=False)
    def test_imgproxy_url_returns_original_url_when_disabled(self):
        image_url = "/media/posts/example.jpg"

        self.assertEqual(imgproxy_url(image_url, 200, 150), image_url)

    @override_settings(
        USE_IMGPROXY=True,
        IMGPROXY_KEY="0000000000000000000000000000000000000000000000000000000000000000",
        IMGPROXY_SALT="0000000000000000000000000000000000000000000000000000000000000000",
        IMGPROXY_BASE_URL="/imgproxy",
    )
    def test_imgproxy_url_signs_original_url_when_enabled(self):
        image_url = "/media/posts/example.jpg"

        result = imgproxy_url(image_url, 200, 150)

        self.assertTrue(result.startswith("/imgproxy/"))
        self.assertIn("/rs:fit:200:150:f:0/", result)
        self.assertTrue(result.endswith(".webp"))
