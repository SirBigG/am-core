from django.test import TestCase, override_settings

from core.adverts.models import Advert
from settings import dev


class FeatureFlagTemplateTests(TestCase):
    def test_dev_settings_disable_adsense_but_keep_internal_adverts(self):
        self.assertFalse(dev.ENABLE_ADVERTS)
        self.assertTrue(dev.ENABLE_INTERNAL_ADVERTS)

    @override_settings(ENABLE_ADVERTS=False, ENABLE_INTERNAL_ADVERTS=True, ENABLE_ANALYTICS=False)
    def test_local_flags_keep_internal_adverts_and_hide_tracking_scripts(self):
        Advert.objects.create(title="test advert", description="test", price=100, contact="test")

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test advert")
        self.assertContains(response, "agromegaConsentConfig")
        self.assertNotContains(response, "data-cookie-consent")
        self.assertNotContains(response, "googletagmanager.com")
        self.assertNotContains(response, "googlesyndication.com")

    @override_settings(ENABLE_ADVERTS=False, ENABLE_INTERNAL_ADVERTS=False, ENABLE_ANALYTICS=False)
    def test_internal_adverts_can_be_hidden_independently(self):
        Advert.objects.create(title="test advert", description="test", price=100, contact="test")

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "test advert")
        self.assertNotContains(response, "data-cookie-consent")

    @override_settings(ENABLE_ADVERTS=True, ENABLE_INTERNAL_ADVERTS=True, ENABLE_ANALYTICS=True)
    def test_live_defaults_render_advert_surfaces_and_consent_gated_tracking(self):
        Advert.objects.create(title="test advert", description="test", price=100, contact="test")

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test advert")
        self.assertContains(response, "data-cookie-consent")
        self.assertContains(response, 'data-cookie-category="analytics"')
        self.assertContains(response, 'data-cookie-category="advertising"')
        self.assertContains(response, "googletagmanager.com")
        self.assertContains(response, "googlesyndication.com")
        self.assertNotContains(response, '<script async src="https://www.googletagmanager.com')
        self.assertNotContains(response, '<script async src="https://pagead2.googlesyndication.com')
