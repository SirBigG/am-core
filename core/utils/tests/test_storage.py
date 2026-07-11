import tempfile

from django.test import SimpleTestCase, override_settings

from core.utils.storage import VersionedStaticFilesStorage, _versioned_url


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

    @override_settings(MEDIA_VERSION=None)
    def test_url_is_not_given_a_none_version(self):
        self.assertEqual(self.storage.url("posts/list.css"), "/static/posts/list.css")

    @override_settings(MEDIA_VERSION="20260711")
    def test_version_is_appended_after_existing_query_parameters(self):
        self.assertEqual(
            _versioned_url("https://static.example.com/site.css?x=1"),
            "https://static.example.com/site.css?x=1&v=20260711",
        )
