from pathlib import Path

from ckeditor.widgets import CKEditorWidget
from django.conf import settings
from django.contrib import admin
from django.test import SimpleTestCase

from core.services.admin import MetaDataAdmin
from core.services.models import MetaData


class MetaDataAdminTests(SimpleTestCase):
    def test_text_uses_shared_article_ckeditor_assets(self):
        model_admin = MetaDataAdmin(MetaData, admin.site)
        form = model_admin.get_form(None)()

        self.assertIsInstance(form.fields["text"].widget, CKEditorWidget)
        self.assertIn("posts/admin/ckeditor-source.css", str(model_admin.media))
        self.assertIn("posts/admin/ckeditor-source.js", str(model_admin.media))

    def test_category_metadata_templates_use_article_body_styles(self):
        template_paths = (
            "core/posts/templates/posts/list.html",
            "core/posts/templates/posts/list_order.html",
            "core/posts/templates/posts/parent_index.html",
            "core/registry/templates/registry/categories.html",
            "core/registry/templates/registry/varieties.html",
        )

        for template_path in template_paths:
            with self.subTest(template=template_path):
                template = Path(settings.BASE_DIR, template_path).read_text()
                self.assertIn('class="site-catalog-hero__text site-article-body"', template)
