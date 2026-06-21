from django.contrib.flatpages.models import FlatPage
from django.test import TestCase


class LegalFlatPagesSeedTests(TestCase):
    def test_legal_flatpages_are_seeded_with_sites(self):
        expected_pages = {
            "/about/": "Про нас",
            "/privacy_policy/": "Політика конфіденційності",
            "/cookies_policy/": "Політика cookies",
            "/terms/": "Умови користування",
            "/publication_rules/": "Правила публікацій і модерації",
            "/adverts_rules/": "Правила оголошень",
        }

        pages = FlatPage.objects.filter(url__in=expected_pages)

        self.assertEqual(pages.count(), len(expected_pages))
        for page in pages:
            self.assertEqual(page.title, expected_pages[page.url])
            self.assertTrue(page.content)
            self.assertTrue(page.sites.exists())

        privacy_policy = FlatPage.objects.get(url="/privacy_policy/")
        self.assertIn("Які дані ми можемо обробляти", privacy_policy.content)
        self.assertIn("Google AdSense", FlatPage.objects.get(url="/cookies_policy/").content)
