from django.db import models

from core.companies.models import CurrencyChoices

"""
Model for storing product prices for different categories, stores, countries and dates.
"""


class Price(models.Model):
    product = models.ForeignKey(
        "companies.Product", on_delete=models.SET_NULL, related_name="prices", blank=True, null=True
    )
    date = models.DateField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    min_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    max_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(choices=CurrencyChoices.choices, default=CurrencyChoices.UAH, blank=True, null=True)

    class Meta:
        verbose_name = "Price"
        verbose_name_plural = "Prices"

    def __str__(self):
        return f"{self.product} {self.price} {self.date}"
