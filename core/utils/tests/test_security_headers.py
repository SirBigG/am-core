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
        self.assertIn("https://www.googletagmanager.com", policy)
        self.assertIn("https://pagead2.googlesyndication.com", policy)
        self.assertIn("style-src 'self' 'unsafe-inline'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertIn("base-uri 'self'", policy)
        self.assertIn("report-uri /csp/report/", policy)

    def test_content_security_policy_report_endpoint_accepts_browser_reports_without_csrf(self):
        csrf_client = self.client_class(enforce_csrf_checks=True)

        with self.assertLogs("django.security.csp", level="INFO"):
            response = csrf_client.post(
                "/csp/report/",
                data='{"csp-report": {"blocked-uri": "inline"}}',
                content_type="application/csp-report",
                HTTP_HOST="localhost:8000",
            )

        self.assertEqual(response.status_code, 204)

    def test_content_security_policy_report_endpoint_requires_post(self):
        response = self.client.get("/csp/report/", HTTP_HOST="localhost:8000")

        self.assertEqual(response.status_code, 405)
