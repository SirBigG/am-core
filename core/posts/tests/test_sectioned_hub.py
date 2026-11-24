from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from core.adverts.models import Advert
from core.classifier.models import Category, CategoryHub, CategoryHubSection
from core.companies.models import Company, Product
from core.posts.models import GuideSection, GuideSectionArticle, Post
from core.utils.tests.factories import CategoryFactory, LocationFactory, PostFactory, StaffUserFactory


@override_settings(
    HOST="https://agromega.in.ua",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class SectionedHubTests(TestCase):
    def setUp(self):
        cache.clear()
        self.root = CategoryFactory()
        self.crop = CategoryFactory(parent=self.root, slug="custom-crop", value="Нова культура")
        self.catalog = CategoryFactory(parent=self.root, slug="legacy-catalog")
        self.guide = CategoryFactory(parent=self.root, slug="legacy-guide")
        self.hub = CategoryHub.objects.create(
            category=self.crop,
            layout="sectioned",
            is_active=True,
            guide_category=self.guide,
            description="Introduction managed in admin",
        )
        self.section = CategoryHubSection.objects.create(hub=self.hub, category=self.catalog, role="varieties")
        self.company = Company.objects.create(
            name="Seller", website="https://seller.example", location=LocationFactory()
        )
        self.cultivar = self.post(self.catalog, "Configured cultivar")
        self.offer(self.cultivar)
        self.url = "/custom-crop/"

    def post(self, category, title, **kwargs):
        post = PostFactory(rubric=category, title=title, **kwargs)
        post.get_absolute_url()
        return post

    def offer(self, post, **kwargs):
        return Product.objects.create(
            company=self.company,
            category=post.rubric,
            post=post,
            name=post.title,
            price=10,
            match_status=Product.MatchStatus.AUTO,
            **kwargs,
        )

    def test_external_catalog_and_strict_market_links_are_rendered(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.cultivar.title)
        self.catalog.refresh_from_db()
        self.assertContains(response, f'href="{self.catalog.absolute_url}"')
        self.assertContains(response, f'href="{self.cultivar.absolute_url}"')
        self.assertContains(response, f'href="{reverse("market:variety", args=[self.cultivar.pk])}?hub=custom-crop"')
        self.assertContains(response, 'href="/agromarket/?hub=custom-crop"')
        self.assertContains(response, 'Побачити всі пропозиції <span class="catalog-arrow-up-right" aria-hidden="true">→</span>', count=2)
        self.assertNotContains(response, "kartoplya")
        self.assertNotContains(response, "kartoplia-sorty")
        self.assertNotContains(response, "potato-hero.jpg")
        self.assertContains(response, "Introduction managed in admin")
        self.assertEqual([p.pk for p in response.context["hub_sections"]["latest_varieties"]], [self.cultivar.pk])

    @override_settings(ENABLE_INTERNAL_ADVERTS=True)
    def test_crop_adverts_link_to_matching_active_offers(self):
        child = CategoryFactory(parent=self.crop)
        for title, category, is_active in [
            ("Crop advert", self.crop, True),
            ("Subcategory advert", child, True),
            ("Unrelated advert", self.catalog, True),
            ("Inactive crop advert", self.crop, False),
        ]:
            Advert.objects.create(
                title=title, category=category, is_active=is_active, description="Description", contact="Contact"
            )

        filtered_url = reverse("adverts:list") + "?category=" + self.crop.slug
        hub = self.client.get(self.url)
        self.assertContains(hub, f'href="{filtered_url}"')
        for response in (hub, self.client.get(filtered_url)):
            self.assertContains(response, "Crop advert")
            self.assertContains(response, "Subcategory advert")
            self.assertNotContains(response, "Unrelated advert")
            self.assertNotContains(response, "Inactive crop advert")

    def test_renaming_catalog_and_crop_requires_no_code_changes(self):
        self.client.get(self.url)  # Populate context cache before admin edits.
        self.catalog.slug = "renamed-catalog"
        self.catalog.save()
        self.crop.slug = "renamed-crop"
        self.crop.save()
        response = self.client.get("/renamed-crop/")
        self.catalog.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{self.catalog.absolute_url}"')
        self.assertContains(response, "?hub=renamed-crop")
        self.assertContains(response, self.cultivar.title)

    def test_separate_market_source_is_independent_of_knowledge_catalog(self):
        market = CategoryFactory(parent=self.root, slug="seller-catalog")
        cultivar = self.post(market, "Market cultivar")
        # Ordinary category market permits a non-exact product title.
        offer = self.offer(cultivar)
        Product.objects.filter(pk=offer.pk).update(name="Packaged cultivar")
        self.hub.market_category = market
        self.hub.save()
        response = self.client.get(self.url)
        data = response.context["hub_sections"]
        self.assertEqual([p.pk for p in data["latest_varieties"]], [self.cultivar.pk])
        self.assertEqual([p.pk for p in data["popular"]], [cultivar.pk])
        self.assertContains(response, "Market cultivar")
        self.assertContains(response, 'href="/agromarket/category/seller-catalog/"')
        self.assertContains(response, f'href="{reverse("market:variety", args=[cultivar.pk])}"')
        self.assertNotContains(response, "?hub=")

    def test_price_rows_identify_cultivars_with_identical_seller_titles(self):
        self.hub.market_category = self.catalog
        self.hub.save()
        other_cultivar = self.post(self.catalog, "Another cultivar")
        self.offer(other_cultivar)
        seller_title = "Посадковий матеріал, 1 кг"
        Product.objects.filter(category=self.catalog).update(name=seller_title)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        prices = response.content.decode().split('id="prices"', 1)[1].split("</section>", 1)[0]
        self.assertInHTML('<th scope="col">Сорт</th>', prices)
        for cultivar in (self.cultivar, other_cultivar):
            with self.subTest(cultivar=cultivar.title):
                row = prices.split(f'<tr data-variety="{cultivar.pk}"', 1)[1].split("</tr>", 1)[0]
                self.assertInHTML(f"<td>{cultivar.title}</td>", row)
                self.assertInHTML(f"<td>{seller_title}</td>", row)

    def test_hidden_explicit_market_never_falls_back_to_knowledge_offers(self):
        ancestor = CategoryFactory(parent=self.root)
        market = CategoryFactory(parent=ancestor, slug="hidden-market")
        self.hub.market_category = market
        self.hub.save()
        for hidden in (market, ancestor):
            Category.objects.filter(pk=hidden.pk).update(is_active=False)
            response = self.client.get(self.url)
            data = response.context["hub_sections"]
            self.assertEqual(data["popular"], [])
            self.assertEqual(list(data["companies"]), [])
            self.assertEqual(data["market_url"], "")
            market_block = response.content.decode().split('id="market"')[1].split("</section>")[0]
            self.assertNotIn('href="/agromarket/', market_block)
            Category.objects.filter(pk=hidden.pk).update(is_active=True)

    def test_guides_use_configured_source_and_exclude_future_draft_and_missing_urls(self):
        current = self.post(self.guide, "Current guide")
        future = self.post(self.guide, "Scheduled guide", publish_date=timezone.now() + timedelta(days=3))
        draft = self.post(self.guide, "Draft guide", status=False)
        missing = self.post(self.guide, "Missing URL guide")
        Post.objects.filter(pk=missing.pk).update(absolute_url="")
        step = GuideSection.objects.create(category=self.guide, title="Curated step")
        for post in (current, future, draft, missing):
            GuideSectionArticle.objects.create(section=step, post=post)
        response = self.client.get(self.url)
        self.assertContains(response, current.title)
        self.assertContains(response, f'href="{current.absolute_url}"')
        for post in (future, draft, missing):
            self.assertNotContains(response, post.title)
        self.guide.refresh_from_db()
        self.assertContains(response, f'href="{self.guide.absolute_url}"')

    def test_guides_on_hub_itself_remain_available(self):
        self.hub.guide_category = None
        self.hub.save()
        guide = self.post(self.crop, "Local guide")
        step = GuideSection.objects.create(category=self.crop, title="Local step")
        GuideSectionArticle.objects.create(section=step, post=guide)
        self.assertContains(self.client.get(self.url), "Local guide")

    def test_hidden_guide_source_is_omitted(self):
        post = self.post(self.guide, "Hidden guide")
        step = GuideSection.objects.create(category=self.guide, title="Hidden step")
        GuideSectionArticle.objects.create(section=step, post=post)
        Category.objects.filter(pk=self.guide.pk).update(is_active=False)
        response = self.client.get(self.url)
        self.assertNotContains(response, post.title)
        self.assertEqual(response.context["hub_sections"]["guide_url"], "")

    def test_dynamic_protection_links_and_labels_follow_admin_configuration(self):
        target = CategoryFactory(parent=self.root, slug="custom-protection")
        section = CategoryHubSection.objects.create(
            hub=self.hub,
            category=target,
            role="protection",
            title="Custom protection label",
            description="Custom help",
        )
        response = self.client.get(self.url)
        target.refresh_from_db()
        self.assertContains(response, f'href="{target.absolute_url}"')
        self.assertContains(response, section.title)
        self.assertContains(response, section.description)
        section.is_active = False
        section.save()
        response = self.client.get(self.url)
        self.assertNotContains(response, section.title)
        protection_block = response.content.decode().split('id="protect"')[1].split("</section>")[0]
        self.assertNotIn(f'href="{target.absolute_url}"', protection_block)

    def test_missing_catalog_has_no_fabricated_destination(self):
        self.section.delete()
        response = self.client.get(self.url)
        self.assertEqual(response.context["hub_sections"]["catalog_url"], "")
        self.assertEqual(response.context["hub_sections"]["latest_varieties"], [])
        self.assertEqual(response.context["hub_sections"]["popular"], [])
        self.assertNotContains(response, "kartoplia-sorty")
        self.assertNotContains(response, 'href=""')

    def test_catalog_descendants_and_filtering_remain_supported(self):
        child = CategoryFactory(parent=self.catalog)
        cultivar = self.post(child, "Descendant cultivar")
        self.offer(cultivar)
        response = self.client.get(self.url, {"q": "Descendant"})
        self.assertEqual([p.pk for p in response.context["hub_sections"]["latest_varieties"]], [cultivar.pk])
        self.assertTrue(response.context["hub_sections"]["latest_varieties"][0].has_offers)

    def test_unverified_offers_do_not_enter_strict_hub(self):
        Product.objects.filter(pk__in=self.company.products.values("pk")).update(name="Unrelated product")
        response = self.client.get(self.url)
        self.assertEqual(response.context["hub_sections"]["popular"], [])
        self.assertFalse(response.context["hub_sections"]["latest_varieties"][0].has_offers)

    def test_layout_can_be_changed_in_admin_and_cache_is_refreshed(self):
        self.client.get(self.url)
        self.client.force_login(StaffUserFactory(is_superuser=True))
        url = reverse("admin:classifier_categoryhub_change", args=[self.hub.pk])
        response = self.client.post(
            url,
            {
                "category": self.crop.pk,
                "layout": "standard",
                "is_active": "on",
                "description": self.hub.description,
                "guide_category": self.guide.pk,
                "market_category": "",
                "site": "",
                "locale": "",
                "sections-TOTAL_FORMS": 0,
                "sections-INITIAL_FORMS": 0,
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.hub.refresh_from_db()
        self.assertEqual(self.hub.layout, "standard")
        self.client.logout()
        response = self.client.get(self.url)
        self.assertNotIn("hub_sections", response.context)
        self.assertNotContains(response, 'class="potato-tabs"')

    def test_hero_upload_in_category_admin_is_uncropped_and_used_in_market(self):
        image = BytesIO()
        Image.new("RGB", (1200, 500), "green").save(image, format="PNG")
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            self.client.force_login(StaffUserFactory(is_superuser=True))
            url = reverse("admin:classifier_category_change", args=[self.crop.pk])
            response = self.client.get(url)
            data = {
                "value": self.crop.value,
                "slug": self.crop.slug,
                "parent": self.root.pk,
                "presentation_mode": "catalog",
                "is_active": "on",
                "_save": "Save",
                "hero_image": SimpleUploadedFile("uploaded-hero.png", image.getvalue(), content_type="image/png"),
            }
            for inline in response.context["inline_admin_formsets"]:
                prefix = inline.formset.prefix
                data.update({f"{prefix}-TOTAL_FORMS": 0, f"{prefix}-INITIAL_FORMS": 0})
            self.assertEqual(self.client.post(url, data).status_code, 302)
            self.crop.refresh_from_db()
            self.assertEqual((self.crop.hero_image.width, self.crop.hero_image.height), (1200, 500))
            self.client.logout()
            self.assertContains(self.client.get(self.url), self.crop.hero_image.url)
            # Each category controls its own market hero, independently of hub image.
            self.catalog.hero_image.name = self.crop.hero_image.name
            self.catalog.save()
            market_url = reverse("market:category", args=[self.catalog.slug])
            self.assertContains(self.client.get(market_url), self.crop.hero_image.url)
            detail_url = reverse("market:variety", args=[self.cultivar.pk])
            self.assertContains(self.client.get(detail_url), self.crop.hero_image.url)
            self.crop.hero_image = ""
            self.crop.save()
            self.assertNotContains(self.client.get(self.url), "uploaded-hero")
            self.assertNotContains(self.client.get(self.url), "potato-hero.jpg")
