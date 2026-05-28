import importlib
import os
from unittest.mock import patch

from django.test import SimpleTestCase


class SecurityHeaderTests(SimpleTestCase):
    def test_security_middleware_headers_are_present_on_service_worker(self):
        response = self.client.get("/service-worker.js", HTTP_HOST="localhost:8000")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Referrer-Policy"], "same-origin")
        self.assertEqual(response.headers["Cross-Origin-Opener-Policy"], "same-origin")

    def test_clickjacking_header_is_present_on_service_worker(self):
        response = self.client.get("/service-worker.js", HTTP_HOST="localhost:8000")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_content_security_policy_report_only_header_is_present(self):
        response = self.client.get("/service-worker.js", HTTP_HOST="localhost:8000")
        policy = response.headers["Content-Security-Policy-Report-Only"]

        self.assertEqual(response.status_code, 200)
        self.assertIn("default-src 'self'", policy)
        self.assertIn("script-src 'self' 'unsafe-inline'", policy)
        self.assertIn("style-src 'self' 'unsafe-inline'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertIn("base-uri 'self'", policy)
        self.assertIn("report-uri /csp/report/", policy)

    def test_content_security_policy_can_include_static_origins_from_env(self):
        with patch.dict(os.environ, {"CSP_STATIC_ORIGINS": "https://static.example.com"}, clear=False):
            import settings.settings as project_settings

            project_settings = importlib.reload(project_settings)

        try:
            policy = project_settings.SECURE_CSP_REPORT_ONLY

            self.assertIn("https://static.example.com", policy["script-src"])
            self.assertIn("https://static.example.com", policy["style-src"])
            self.assertIn("https://static.example.com", policy["font-src"])
        finally:
            importlib.reload(project_settings)

    def test_content_security_policy_can_include_directive_origins_from_env(self):
        env = {
            "CSP_SCRIPT_SRC_ORIGINS": "https://scripts.example.com",
            "CSP_STYLE_SRC_ORIGINS": "https://styles.example.com",
            "CSP_FONT_SRC_ORIGINS": "https://fonts.example.com",
            "CSP_FRAME_SRC_ORIGINS": "https://frames.example.com",
            "CSP_FORM_ACTION_ORIGINS": "https://forms.example.com",
        }
        with patch.dict(os.environ, env, clear=False):
            import settings.settings as project_settings

            project_settings = importlib.reload(project_settings)

        try:
            policy = project_settings.SECURE_CSP_REPORT_ONLY

            self.assertIn("https://scripts.example.com", policy["script-src"])
            self.assertIn("https://styles.example.com", policy["style-src"])
            self.assertIn("https://fonts.example.com", policy["font-src"])
            self.assertIn("https://frames.example.com", policy["frame-src"])
            self.assertIn("https://forms.example.com", policy["form-action"])
        finally:
            importlib.reload(project_settings)

    def test_content_security_policy_report_endpoint_accepts_browser_reports_without_csrf(self):
        csrf_client = self.client_class(enforce_csrf_checks=True)

        with self.assertLogs("django.security.csp", level="INFO") as logs:
            response = csrf_client.post(
                "/csp/report/",
                data='{"csp-report": {"blocked-uri": "inline"}}',
                content_type="application/csp-report",
                HTTP_HOST="localhost:8000",
            )

        self.assertEqual(response.status_code, 204)
        self.assertIn('"blocked-uri": "inline"', logs.output[0])

    def test_content_security_policy_report_endpoint_requires_post(self):
        response = self.client.get("/csp/report/", HTTP_HOST="localhost:8000")

        self.assertEqual(response.status_code, 405)
