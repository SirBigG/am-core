from django.template import Context, Template
from django.test import SimpleTestCase, override_settings


class StaticPushTemplateTagTests(SimpleTestCase):
    @override_settings(STATIC_URL="/static/")
    def test_static_push_returns_static_asset_url(self):
        rendered = Template("{% load static_push %}{% static_push 'favicon.ico' %}").render(Context())

        self.assertEqual(rendered, "/static/favicon.ico")
