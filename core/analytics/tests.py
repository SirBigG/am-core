import gzip
import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.analytics import nginx_logs
from core.analytics.models import Price
from core.analytics.nginx_logs import (
    InvalidDateRange,
    LogDirectoryUnavailable,
    ScanLimitExceeded,
    clear_report_cache,
    discover_log_files,
    get_report,
    redact_error_message,
)
from core.utils.tests.factories import StaffUserFactory, UserFactory

TODAY = date.today()


def access_row(**overrides):
    row = {
        "time": f"{TODAY.isoformat()}T10:00:00+00:00",
        "method": "GET",
        "path": "/catalog/?token=secret",
        "status": 200,
        "bytes": 123,
        "request_time": 0.25,
        "referrer": "https://example.com/source?email=private",
        "user_agent": "Test Browser <script>",
    }
    row.update(overrides)
    return json.dumps(row)


class NginxLogServiceTests(SimpleTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        clear_report_cache()

    def write(self, name, content, compressed=False):
        path = Path(self.tempdir.name, name)
        if compressed:
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                stream.write(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def settings(self, **overrides):
        values = {
            "NGINX_ANALYTICS_LOG_DIR": self.tempdir.name,
            "NGINX_ANALYTICS_MAX_DAYS": 60,
            "NGINX_ANALYTICS_MAX_SCAN_BYTES": 1_000_000,
            "NGINX_ANALYTICS_MAX_DECOMPRESSED_BYTES": 1_000_000,
            "NGINX_ANALYTICS_MAX_LINES": 1_000,
            "NGINX_ANALYTICS_MAX_LINE_BYTES": 16_384,
            "NGINX_ANALYTICS_MAX_UNIQUE_VALUES": 100,
            "NGINX_ANALYTICS_CACHE_TTL": 180,
            "NGINX_ANALYTICS_TOP_LIMIT": 20,
            "NGINX_ANALYTICS_ERROR_SAMPLE_LIMIT": 20,
        }
        values.update(overrides)
        return override_settings(**values)

    def test_discovers_only_allowlisted_files(self):
        self.write("traffic.log", "")
        self.write(f"traffic.log-{TODAY.isoformat()}.gz", "", compressed=True)
        self.write(f"application-error.log-{TODAY.isoformat()}", "")
        self.write("traffic.log.backup", "")
        self.write("secrets.txt", "")
        with self.settings():
            files = discover_log_files(TODAY, TODAY)
        self.assertEqual(len(files), 3)
        self.assertEqual({item.kind for item in files}, {"access", "error"})

    def test_rejects_symlinks(self):
        outside = Path(self.tempdir.name).parent / "outside-nginx-analytics.log"
        outside.write_text(access_row(), encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        os.symlink(outside, Path(self.tempdir.name, "traffic.log"))
        with self.settings():
            self.assertEqual(discover_log_files(TODAY, TODAY), [])

    def test_rejects_missing_directory_long_range_and_byte_budget(self):
        with override_settings(NGINX_ANALYTICS_LOG_DIR="/definitely/missing/nginx"):
            with self.assertRaises(LogDirectoryUnavailable):
                discover_log_files(TODAY, TODAY)
        with self.settings(NGINX_ANALYTICS_MAX_DAYS=2):
            with self.assertRaises(InvalidDateRange):
                discover_log_files(TODAY - timedelta(days=2), TODAY)
        self.write("traffic.log", "large")
        with self.settings(NGINX_ANALYTICS_MAX_SCAN_BYTES=1):
            with self.assertRaises(ScanLimitExceeded):
                discover_log_files(TODAY, TODAY)

    def test_aggregates_plain_and_gzipped_access_logs(self):
        self.write("traffic.log", access_row() + "\nnot-json\n")
        self.write(
            f"traffic.log-{TODAY.isoformat()}.gz",
            access_row(method="POST", status=503, bytes=77, request_time=2.5) + "\n",
            compressed=True,
        )
        with self.settings():
            report = get_report(TODAY, TODAY)
        self.assertEqual(report["access"]["total_requests"], 2)
        self.assertEqual(report["access"]["response_bytes"], 200)
        self.assertEqual(report["access"]["malformed"], 1)
        self.assertIn(("/catalog/", 2), report["access"]["paths"])
        self.assertIn(("5xx", 1), report["access"]["status_classes"])
        self.assertEqual(report["access"]["slow_paths"][0], ("/catalog/", 1.375, 2))
        self.assertNotIn("secret", repr(report))

    def test_status_filter_and_line_limit(self):
        self.write("traffic.log", "\n".join([access_row(status=200), access_row(status=404), access_row(status=500)]))
        with self.settings(NGINX_ANALYTICS_MAX_LINES=2):
            report = get_report(TODAY, TODAY, "4xx")
        self.assertEqual(report["access"]["total_requests"], 1)
        self.assertTrue(report["truncated"])
        self.assertEqual(report["lines_scanned"], 2)

    def test_parses_and_redacts_native_error_logs(self):
        self.write(
            "application-error.log",
            f"{TODAY.strftime('%Y/%m/%d')} 10:02:03 [error] 7#7: *1 upstream timed out, "
            'client: 192.168.1.10, request: "GET /private?token=abc HTTP/1.1", '
            'password=hunter2, open() "/srv/private/file" failed\n'
            "malformed line\n",
        )
        with self.settings():
            report = get_report(TODAY, TODAY)
        self.assertEqual(report["errors"]["total"], 1)
        self.assertEqual(report["errors"]["malformed"], 1)
        self.assertIn(("timeout", 1), report["errors"]["categories"])
        rendered = repr(report["errors"]["recent"])
        self.assertNotIn("abc", rendered)
        self.assertNotIn("hunter2", rendered)
        self.assertNotIn("/srv/private", rendered)
        self.assertNotIn("192.168.1.10", rendered)

    def test_redaction_handles_urls_credentials_and_paths(self):
        result = redact_error_message(
            "authorization: Bearer eyJhbGciOiJIUzI1NiJ9.secret, "
            "cookie: sessionid=first; csrftoken=second, "
            "https://site.test/a?token=abc /var/lib/nginx/private/file /etc/passwd"
        )
        self.assertNotIn("eyJ", result)
        self.assertNotIn("sessionid", result)
        self.assertNotIn("csrftoken", result)
        self.assertNotIn("token=abc", result)
        self.assertNotIn("/var/lib", result)
        self.assertNotIn("/etc/passwd", result)

    def test_cache_bounds_live_file_staleness_until_cleared(self):
        path = self.write("traffic.log", access_row() + "\n")
        original = nginx_logs._build_report
        with self.settings(), patch("core.analytics.nginx_logs._build_report", wraps=original) as build:
            first = get_report(TODAY, TODAY)
            again = get_report(TODAY, TODAY)
            path.write_text(access_row() + "\n" + access_row() + "\n", encoding="utf-8")
            cached_after_append = get_report(TODAY, TODAY)
            clear_report_cache()
            refreshed = get_report(TODAY, TODAY)
        self.assertIs(first, again)
        self.assertIs(first, cached_after_append)
        self.assertEqual(first["access"]["total_requests"], 1)
        self.assertEqual(refreshed["access"]["total_requests"], 2)
        self.assertEqual(build.call_count, 2)

    def test_bounds_decompression_line_size_cardinality_and_error_samples(self):
        unique_rows = "\n".join(access_row(path=f"/unique/{index}") for index in range(5)) + "\n"
        self.write("traffic.log", unique_rows + ("x" * 1_000) + "\n")
        errors = "".join(
            f"{TODAY.strftime('%Y/%m/%d')} 10:02:0{index} [error] 7#7: *1 message {index}\n" for index in range(5)
        )
        self.write("application-error.log", errors)
        with self.settings(
            NGINX_ANALYTICS_MAX_LINE_BYTES=512,
            NGINX_ANALYTICS_MAX_UNIQUE_VALUES=2,
            NGINX_ANALYTICS_ERROR_SAMPLE_LIMIT=2,
        ):
            report = get_report(TODAY, TODAY)
        self.assertLessEqual(len(report["access"]["paths"]), 2)
        self.assertLessEqual(len(report["errors"]["messages"]), 2)
        self.assertEqual(len(report["errors"]["recent"]), 2)
        self.assertGreater(report["oversized_lines"], 0)
        self.assertGreater(report["cardinality_limited"], 0)

    def test_gzip_expansion_is_bounded_by_decompressed_bytes(self):
        self.write(
            f"traffic.log-{TODAY.isoformat()}.gz",
            (access_row() + "\n") * 100,
            compressed=True,
        )
        with self.settings(NGINX_ANALYTICS_MAX_DECOMPRESSED_BYTES=500):
            report = get_report(TODAY, TODAY)
        self.assertTrue(report["truncated"])
        self.assertEqual(report["truncation_reason"], "decompressed byte limit")
        self.assertLess(report["access"]["total_requests"], 100)


@override_settings(
    NGINX_ANALYTICS_MAX_DAYS=60,
    NGINX_ANALYTICS_MAX_SCAN_BYTES=1_000_000,
    NGINX_ANALYTICS_MAX_DECOMPRESSED_BYTES=1_000_000,
    NGINX_ANALYTICS_MAX_LINES=1_000,
    NGINX_ANALYTICS_MAX_LINE_BYTES=16_384,
    NGINX_ANALYTICS_MAX_UNIQUE_VALUES=100,
    NGINX_ANALYTICS_CACHE_TTL=180,
    NGINX_ANALYTICS_TOP_LIMIT=20,
    NGINX_ANALYTICS_ERROR_SAMPLE_LIMIT=20,
)
class NginxAnalyticsAdminTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.override = override_settings(NGINX_ANALYTICS_LOG_DIR=self.tempdir.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        clear_report_cache()
        Path(self.tempdir.name, "traffic.log").write_text(access_row() + "\n", encoding="utf-8")
        self.url = reverse("admin:analytics_nginxanalyticsdashboard_changelist")

    def test_anonymous_redirects_and_non_staff_cannot_access(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(UserFactory())
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_staff_without_permission_is_denied(self):
        self.client.force_login(StaffUserFactory())
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_authorized_staff_and_superuser_can_view_report(self):
        staff = StaffUserFactory()
        staff.user_permissions.add(Permission.objects.get(codename="view_nginx_analytics"))
        self.client.force_login(staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "NGINX analytics")
        self.assertContains(response, "requests")
        self.client.force_login(StaffUserFactory(is_superuser=True))
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_response_is_never_cached_and_anchor_table_is_not_queried(self):
        self.client.force_login(StaffUserFactory(is_superuser=True))
        before = Price.objects.count()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url)
        self.assertIn("no-cache", response.headers["Cache-Control"])
        self.assertEqual(Price.objects.count(), before)
        sql = " ".join(query["sql"].lower() for query in queries.captured_queries)
        self.assertNotIn("nginxanalyticsdashboard", sql)
        self.assertNotIn("insert into", sql)
        self.assertNotIn("update ", sql)

    def test_non_report_routes_are_forbidden_without_querying_an_anchor_table(self):
        self.client.force_login(StaffUserFactory(is_superuser=True))
        urls = (
            reverse("admin:analytics_nginxanalyticsdashboard_add"),
            reverse("admin:analytics_nginxanalyticsdashboard_change", args=(1,)),
            reverse("admin:analytics_nginxanalyticsdashboard_delete", args=(1,)),
            reverse("admin:analytics_nginxanalyticsdashboard_history", args=(1,)),
        )
        with CaptureQueriesContext(connection) as queries:
            responses = [self.client.get(url) for url in urls]
        self.assertEqual([response.status_code for response in responses], [403, 403, 403, 403])
        sql = " ".join(query["sql"].lower() for query in queries.captured_queries)
        self.assertNotIn("nginxanalyticsdashboard", sql)

    def test_bounded_filter_and_missing_volume_errors_are_safe(self):
        self.client.force_login(StaffUserFactory(is_superuser=True))
        response = self.client.get(self.url, {"start": "2025-01-01", "end": "2026-01-01"})
        self.assertContains(response, "cannot exceed 60 days")
        with override_settings(NGINX_ANALYTICS_LOG_DIR="/missing/private/logs"):
            response = self.client.get(self.url)
        self.assertContains(response, "log directory is unavailable")

    def test_admin_index_link_is_permission_protected(self):
        staff = StaffUserFactory()
        self.client.force_login(staff)
        response = self.client.get(reverse("admin:index"))
        self.assertNotContains(response, self.url)
        staff.user_permissions.add(Permission.objects.get(codename="view_nginx_analytics"))
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, self.url)
