from ckeditor.widgets import CKEditorWidget
from django.contrib import admin
from django.test import TestCase

from core.posts.admin import PostAdmin
from core.posts.models import Post


class AdminPostFormTests(TestCase):
    def test_sources_uses_ckeditor_widget(self):
        form = PostAdmin.form()

        self.assertIsInstance(form.fields["sources"].widget, CKEditorWidget)


class PostAdminTests(TestCase):
    def test_source_mode_assets_are_included(self):
        model_admin = PostAdmin(Post, admin.site)
        media = str(model_admin.media)

        self.assertIn("posts/admin/ckeditor-source.css", media)
        self.assertIn("posts/admin/ckeditor-source.js", media)
