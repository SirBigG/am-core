from django.db import models
from django.urls import reverse
from django.utils.translation import get_language
from transliterate import slugify

from core.classifier.models import Location
from core.posts.models import Post


class Company(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True, null=True, unique=True)
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to="companies", blank=True, null=True)
    active = models.BooleanField(default=True)
    website = models.URLField()
    location = models.ForeignKey(Location, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name.lower(), get_language())
        super().save(*args, **kwargs)

    def get_slug(self):
        return self.slug or slugify(self.name.lower(), get_language())

    def get_absolute_url(self):
        return reverse("companies:detail", args=[self.get_slug(), str(self.id)])


class CurrencyChoices(models.TextChoices):
    UAH = "UAH", "Ukrainian Hryvnia"
    USD = "USD", "United States Dollar"
    EUR = "EUR", "Euro"
    GBP = "GBP", "British Pound Sterling"


class Product(models.Model):
    name = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    company = models.ForeignKey(Company, related_name="products", on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.SET_NULL, blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    active = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(choices=CurrencyChoices.choices, default=CurrencyChoices.UAH, blank=True, null=True)
    auction_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    auction_currency = models.CharField(
        choices=CurrencyChoices.choices, default=CurrencyChoices.UAH, blank=True, null=True
    )
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or self.description
