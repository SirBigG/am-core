from pathlib import Path

from ckeditor.fields import RichTextField
from ckeditor.widgets import CKEditorWidget
from django.conf import settings
from django.test import SimpleTestCase

from core.adverts.forms import AdvertForm
from core.diary.models import Diary, DiaryItem, Plant
from core.events.forms import EventAddForm
from core.events.models import Event
from core.posts.forms import PostForm, UpdatePostForm
from core.posts.models import Post
from core.services.models import MetaData


class CKEditorConfigurationTests(SimpleTestCase):
    def test_ckeditor_static_and_upload_paths_are_configured(self):
        self.assertEqual(settings.CKEDITOR_BASEPATH, "/static/ckeditor/ckeditor/")
        self.assertEqual(settings.CKEDITOR_UPLOAD_PATH, "/media/ckeditor/")
        self.assertIn("public", settings.CKEDITOR_CONFIGS)
        self.assertEqual(settings.CKEDITOR_CONFIGS["default"]["language"], "uk")
        self.assertEqual(settings.CKEDITOR_CONFIGS["default"]["stylesSet"], settings.CKEDITOR_ARTICLE_STYLES)
        self.assertEqual(
            settings.CKEDITOR_CONFIGS["default"]["extraAllowedContent"],
            "div(article-note,important-note,article-faq-item,article-sources);",
        )
        self.assertEqual(settings.CKEDITOR_CONFIGS["public"]["width"], "100%")
        self.assertEqual(settings.CKEDITOR_CONFIGS["public"]["removePlugins"], "exportpdf")
        self.assertEqual(
            settings.CKEDITOR_CONFIGS["public"]["toolbar_Full"],
            [["Styles", "Format", "Bold", "Italic", "Undo", "Redo", "-", "NumberedList", "BulletedList"]],
        )
        self.assertEqual(settings.CKEDITOR_CONFIGS["public"]["stylesSet"], settings.CKEDITOR_ARTICLE_STYLES)
        self.assertEqual(
            settings.CKEDITOR_CONFIGS["public"]["extraAllowedContent"],
            "div(article-note,important-note,article-faq-item,article-sources);",
        )
        self.assertIn(
            {"name": "Джерела", "element": "div", "attributes": {"class": "article-sources"}},
            settings.CKEDITOR_ARTICLE_STYLES,
        )

    def test_public_forms_use_ckeditor_widget_for_rich_text_fields(self):
        forms_and_fields = (
            (PostForm(), "text"),
            (UpdatePostForm(), "text"),
            (EventAddForm(), "text"),
            (AdvertForm(), "description"),
        )

        for form, field_name in forms_and_fields:
            with self.subTest(form=form.__class__.__name__, field=field_name):
                widget = form.fields[field_name].widget
                self.assertIsInstance(widget, CKEditorWidget)
                self.assertEqual(widget.config_name, "public")
                self.assertEqual(widget.attrs["class"], "form-control")

    def test_rendered_ckeditor_widget_keeps_custom_template_contract(self):
        form = PostForm()

        html = form.fields["text"].widget.render("text", "<p>Hello</p>", attrs={"id": "id_text"})

        self.assertIn('class="django-ckeditor-widget"', html)
        self.assertIn('data-field-id="id_text"', html)
        self.assertIn('data-type="ckeditortype"', html)
        self.assertIn("data-config=", html)
        self.assertIn("&lt;p&gt;Hello&lt;/p&gt;", html)
        self.assertIn(".cke_source", html)
        self.assertIn("-webkit-text-fill-color: #111", html)
        self.assertIn("article-note", html)
        self.assertIn("important-note", html)
        self.assertIn("article-faq-item", html)
        self.assertIn("article-sources", html)

    def test_admin_ckeditor_source_asset_previews_article_tables(self):
        script = Path(settings.BASE_DIR, "core/posts/static/posts/admin/ckeditor-source.js").read_text()

        self.assertIn("#dcefd7", script)
        self.assertIn("border-collapse: collapse", script)
        self.assertIn("width: 100% !important", script)
        self.assertIn("table-layout: fixed !important", script)
        self.assertIn("width: auto !important", script)
        self.assertIn("thead th, table th", script)
        self.assertNotIn("table tr:first-child td", script)
        self.assertIn("article-faq-item", script)
        self.assertIn("article-sources a", script)
        self.assertIn("wrapSelectionInFaqBlock", script)
        self.assertIn(".article-faq-item > p:first-child", script)
        self.assertIn("FAQ блок", script)
        self.assertIn("Звичайний текст", script)
        self.assertIn("removeArticleStyles", script)
        self.assertIn("ensureArticleToolbarStyles", script)
        self.assertIn("agro-editor-style-button", script)
        self.assertIn('addEventListener("mousedown"', script)

    def test_models_keep_rich_text_fields_for_editor_content(self):
        models_and_fields = (
            (Post, "text"),
            (Event, "text"),
            (MetaData, "text"),
            (Diary, "description"),
            (Plant, "description"),
            (DiaryItem, "description"),
        )

        for model, field_name in models_and_fields:
            with self.subTest(model=model.__name__, field=field_name):
                self.assertIsInstance(model._meta.get_field(field_name), RichTextField)
