import json
from types import SimpleNamespace

from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from lxml import html

from core.posts.admin import PostAdmin
from core.posts.metadata import resolve_publication_metadata
from core.posts.models import Post
from core.utils.tests.factories import CategoryFactory, MetaDataFactory, PostFactory, StaffUserFactory


class MetadataResolverTests(SimpleTestCase):
    def test_blank_values_fall_back_and_normalize_article_text(self):
        for empty in (None, "", " \n\t "):
            post = SimpleNamespace(
                title="Гала",
                meta_title=empty,
                meta_description=empty,
                text="<p>Перша&nbsp; частина &amp; друга.</p>\n<p>Опис.</p>",
            )
            self.assertEqual(
                resolve_publication_metadata(post), {"title": "Гала", "description": "Перша частина & друга. Опис."}
            )

    def test_explicit_metadata_and_empty_or_long_body(self):
        post = SimpleNamespace(
            title="Гала", meta_title="  Гала: опис  ", meta_description="  Опис сорту  ", text="Body"
        )
        self.assertEqual(resolve_publication_metadata(post), {"title": "Гала: опис", "description": "Опис сорту"})
        post.meta_description = None
        post.text = ""
        self.assertEqual(resolve_publication_metadata(post)["description"], "")
        post.text = "<p>" + "Опис " * 100 + "</p>"
        self.assertEqual(len(resolve_publication_metadata(post)["description"]), 160)


@override_settings(HOST="https://agromega.in.ua")
class PublicationMetadataTests(TestCase):
    def setUp(self):
        self.category = CategoryFactory(parent=CategoryFactory())
        self.post = PostFactory(rubric=self.category, title="Гала", text="<p>Текст для опису.</p>")
        self.url = self.post.get_absolute_url()

    def check_surfaces(self, title, description):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        document = html.fromstring(response.content)
        self.assertEqual(document.xpath("string(//title)").strip(), title)
        self.assertEqual(document.xpath("string(//h1)").strip(), title)
        for attribute, key, expected in (
            ("name", "description", description),
            ("property", "og:title", title),
            ("property", "og:description", description),
            ("name", "twitter:title", title),
            ("name", "twitter:description", description),
        ):
            self.assertEqual(document.xpath(f'//meta[@{attribute}="{key}"]/@content'), [expected])
        article = next(
            json.loads(text)
            for text in document.xpath('//script[@type="application/ld+json"]/text()')
            if json.loads(text).get("@type") == "Article"
        )
        self.assertEqual(article["headline"], title)
        self.assertEqual(article["description"], description)
        self.assertEqual(document.xpath("//*[@data-publication-actions]/@data-title"), [title])
        canonical = "https://agromega.in.ua" + self.url
        self.assertEqual(document.xpath('//link[@rel="canonical"]/@href'), [canonical])
        self.assertEqual(document.xpath('//meta[@property="og:url"]/@content'), [canonical])
        self.assertEqual(article["mainEntityOfPage"], canonical)
        breadcrumbs = document.xpath('//*[@aria-label="breadcrumb"]')[0].text_content()
        self.assertIn("Гала", breadcrumbs)
        return document

    def test_explicit_fields_are_used_consistently_and_are_escaped(self):
        self.post.meta_title = 'Гала <особлива> "&"'
        self.post.meta_description = 'Опис </script><script>alert("x")</script> & "цитата"'
        self.post.meta = MetaDataFactory(title="Legacy title", description="Legacy description")
        self.post.save()
        document = self.check_surfaces(self.post.meta_title, self.post.meta_description)
        self.assertNotIn('alert("x")', document.xpath("//script[not(@type)]/text()"))
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Гала")
        self.assertEqual(self.post.get_absolute_url(), self.url)

    def test_empty_metadata_ignores_archive_and_uses_independent_fallbacks(self):
        self.post.meta = MetaDataFactory(title="Legacy title", description="Legacy description")
        self.post.meta_title = "  "
        self.post.meta_description = None
        self.post.save()
        self.check_surfaces("Гала", "Текст для опису.")
        self.post.meta_description = "Окремий опис"
        self.post.save()
        self.check_surfaces("Гала", "Окремий опис")
        self.post.meta_title = "Мета-заголовок"
        self.post.meta_description = ""
        self.post.save()
        self.check_surfaces("Мета-заголовок", "Текст для опису.")

    def test_deleting_archived_metadata_does_not_delete_publication(self):
        legacy = MetaDataFactory()
        self.post.meta = legacy
        self.post.meta_title = "Прямий заголовок"
        self.post.save()
        legacy.delete()
        self.post.refresh_from_db()
        self.assertIsNone(self.post.meta_id)
        self.assertEqual(self.post.meta_title, "Прямий заголовок")

    def test_admin_has_direct_optional_metadata_group(self):
        request = RequestFactory().get("/admin/posts/post/")
        request.user = StaffUserFactory()
        model_admin = PostAdmin(Post, admin.site)
        fieldsets = dict(model_admin.get_fieldsets(request, self.post))
        self.assertEqual(fieldsets["Метадані публікації"]["fields"], ("meta_title", "meta_description"))
        form = model_admin.get_form(request, self.post)(instance=self.post)
        self.assertNotIn("meta", form.fields)
        self.assertNotIn("page_h1", form.fields)
        self.assertFalse(form.fields["meta_title"].required)
        self.assertFalse(form.fields["meta_description"].required)

    def test_canonical_uses_publication_url_even_on_an_alias_path(self):
        alias = self.url.replace(self.post.slug, "obsolete-slug")
        response = self.client.get(alias + "?utm_source=example")
        self.assertEqual(response.status_code, 200)
        document = html.fromstring(response.content)
        expected = "https://agromega.in.ua" + self.url
        self.assertEqual(document.xpath('//link[@rel="canonical"]/@href'), [expected])
        self.assertEqual(document.xpath('//meta[@property="og:url"]/@content'), [expected])

    def test_social_images_use_main_photo_or_site_fallback(self):
        from core.utils.tests.factories import PhotoFactory

        for with_photo in (False, True):
            if with_photo:
                PhotoFactory(post=self.post)
            response = self.client.get(self.url)
            image_url = response.context["publication_image_url"]
            if with_photo:
                self.assertEqual(image_url, response.context["main_photo_full_url"])
            else:
                self.assertTrue(image_url.endswith("/posts/og-default.png"))
            document = html.fromstring(response.content)
            self.assertEqual(document.xpath('//meta[@property="og:image"]/@content'), [image_url])
            self.assertEqual(document.xpath('//meta[@name="twitter:image"]/@content'), [image_url])
            article = next(
                json.loads(text)
                for text in document.xpath('//script[@type="application/ld+json"]/text()')
                if json.loads(text).get("@type") == "Article"
            )
            self.assertEqual(article["image"], [image_url])
