from django.contrib.sites.models import Site
from django.contrib.staticfiles import finders
from django.test import TestCase


class DjangoAdminThemeTests(TestCase):
    def test_admin_theme_static_file_is_available(self):
        self.assertIsNotNone(finders.find("admin/agromega-theme.css"))

    def test_admin_login_loads_agromega_theme_stylesheet(self):
        Site.objects.update_or_create(
            id=1,
            defaults={"domain": "localhost:8000", "name": "localhost"},
        )

        response = self.client.get("/admin/login/", {"next": "/admin/"}, headers={"host": "localhost:8000"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "admin/agromega-theme.css")
