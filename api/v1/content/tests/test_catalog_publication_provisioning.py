from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.catalog.relations import EntityPresentationSelection
from core.catalog.tests.test_public_blocks import PublicBlockFixtures
from core.classifier.publication_checks import SiteCategoryConfiguration, SiteContentPolicy
from core.companies.models import Company, Product, RelatedOfferPublication
from core.posts.models import Post
from core.posts.publication_checks import PostPublicationApproval, SitePostPublication, material_digest
from core.utils.tests.factories import LocationFactory, StaffUserFactory


class CatalogPublicationProvisioningTests(PublicBlockFixtures, TestCase):
    def test_bootstrap_resolves_hub_scope_and_enables_scoped_seller(self):
        posts = list(Post.objects.filter(entity__in=[self.preparation, self.target]))
        post = next(post for post in posts if post.entity_id == self.preparation.pk)
        seller = Company.objects.create(name="Fixture seller", location=LocationFactory())
        product = Product.objects.create(
            post=post,
            category=post.rubric,
            company=seller,
            name="Fixture offer",
            price=50,
            currency="UAH",
            match_status=Product.MatchStatus.CONFIRMED,
            price_updated_at=timezone.now(),
        )
        EntityPresentationSelection.objects.filter(site=self.site).delete()
        SitePostPublication.objects.filter(site=self.site).delete()
        Post.objects.filter(pk=post.pk).update(text="Current material for review")
        post.refresh_from_db()
        SiteCategoryConfiguration.objects.filter(site=self.site).delete()
        SiteContentPolicy.objects.filter(site=self.site).delete()

        operator = APIClient()
        token = Token.objects.create(user=StaffUserFactory(is_superuser=True))
        operator.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        url = reverse("catalog-provision-publications")
        manifest = {
            "site_grant_id": self.site_grant.pk,
            "content_locale": "uk",
            "category_ids": [self.category.pk],
            "posts": [{"id": item.pk, "digest": material_digest(item)} for item in posts],
            "offers": [{"id": product.pk, "package_label": "5 л"}],
            "review_reference": "Fixture review",
        }
        self.assertEqual(self.client.get(self.blocks_url).status_code, 404)
        invalid = operator.post(
            url, {**manifest, "offers": [{"id": product.pk + 1, "package_label": "5 л"}]}, format="json"
        )
        self.assertEqual(invalid.status_code, 409, invalid.data)
        self.assertFalse(SiteContentPolicy.objects.filter(site=self.site).exists())

        created = operator.post(url, manifest, format="json")
        self.assertEqual(created.status_code, 200, created.data)
        replay = operator.post(url, manifest, format="json")
        self.assertEqual(replay.data, created.data)
        self.assertEqual(RelatedOfferPublication.objects.filter(product=product).count(), 1)
        self.assertTrue(
            PostPublicationApproval.objects.filter(post=post, content_digest=material_digest(post)).exists()
        )
        self.assertEqual(self.client.get(self.blocks_url).status_code, 200)
        self.approved_record()
        self.activate(self.save())
        filtered = self.anonymous.get(self.api_url(), {"catalog_1_target": str(self.target.pk)}).json()
        (card,) = filtered["blocks"][0]["selection"]["results"]
        offer_url = card["market"]["url"]
        response = self.anonymous.get(offer_url)
        self.assertContains(response, "Fixture seller")
        self.assertContains(response, "5 л")
        self.assertContains(response, "UAH")
