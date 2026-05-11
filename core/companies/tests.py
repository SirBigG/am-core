from django.test import TestCase
from django.urls import reverse

from core.companies.models import Company, CompanyType, Product
from core.utils.tests.factories import LocationFactory


class CompanyPublicViewTests(TestCase):
    def setUp(self):
        self.location = LocationFactory()
        self.company = Company.objects.create(
            name="Agro Shop",
            type=CompanyType.SHOP,
            description="Seeds and tools",
            active=True,
            website="https://shop.example.com",
            location=self.location,
        )

    def test_company_list_renders_active_shops(self):
        Company.objects.create(
            name="Inactive Shop",
            type=CompanyType.SHOP,
            description="Hidden",
            active=False,
            website="https://hidden.example.com",
            location=self.location,
        )
        Company.objects.create(
            name="Service Company",
            type=CompanyType.SERVICE,
            description="Service",
            active=True,
            website="https://service.example.com",
            location=self.location,
        )

        response = self.client.get(reverse("companies:list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "companies/list.html")
        self.assertEqual(list(response.context["companies"]), [self.company])

    def test_company_detail_renders_products(self):
        product = Product.objects.create(
            company=self.company,
            name="Corn seed",
            description="Hybrid seed",
            price="100.00",
        )

        response = self.client.get(self.company.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "companies/detail.html")
        self.assertEqual(response.context["company"], self.company)
        self.assertIn(product, response.context["products"])

    def test_company_detail_returns_404_for_unknown_company(self):
        response = self.client.get("/companies/missing-999.html")

        self.assertEqual(response.status_code, 404)
