import tempfile

from django.test import SimpleTestCase, override_settings

from core.utils.storage import VersionedStaticFilesStorage


class VersionedStaticFilesStorageTests(SimpleTestCase):
    def setUp(self):
        self.static_dir = tempfile.TemporaryDirectory()
        self.storage = VersionedStaticFilesStorage(location=self.static_dir.name, base_url="/static/")

    def tearDown(self):
        self.static_dir.cleanup()

    @override_settings(MEDIA_VERSION="20260512")
    def test_url_adds_media_version_query_parameter(self):
        self.assertEqual(self.storage.url("posts/list.css"), "/static/posts/list.css?v=20260512")

    @override_settings(MEDIA_VERSION="20260512")
    def test_url_does_not_version_ckeditor_assets(self):
        self.assertEqual(
            self.storage.url("ckeditor/ckeditor/ckeditor.js"),
            "/static/ckeditor/ckeditor/ckeditor.js",
        )
