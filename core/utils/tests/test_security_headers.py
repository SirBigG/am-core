from django.test import SimpleTestCase

from core.utils.security import ContentSecurityPolicyReportOnlyMiddleware


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
        self.assertIn("https://www.googletagmanager.com", policy)
        self.assertIn("https://pagead2.googlesyndication.com", policy)
        self.assertIn("style-src 'self' 'unsafe-inline'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertIn("base-uri 'self'", policy)


class ContentSecurityPolicyReportOnlyMiddlewareTests(SimpleTestCase):
    def test_policy_serializer_keeps_directive_order(self):
        policy = {
            "default-src": ("'self'",),
            "object-src": ("'none'",),
            "upgrade-insecure-requests": (),
        }

        serialized = ContentSecurityPolicyReportOnlyMiddleware._serialize_policy(policy)

        self.assertEqual(serialized, "default-src 'self'; object-src 'none'; upgrade-insecure-requests")
