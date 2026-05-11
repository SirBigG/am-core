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
