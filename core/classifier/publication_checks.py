"""Explicit category and locale eligibility for relation presentation
anchors."""

from django.db import models

from .models import Category


class SiteContentPolicy(models.Model):
    site = models.OneToOneField("sites.Site", primary_key=True, on_delete=models.PROTECT)
    active = models.BooleanField(default=False)
    content_locales = models.JSONField(default=list)
    allow_legacy_und = models.BooleanField(default=False)


class SiteCategoryConfiguration(models.Model):
    site = models.ForeignKey("sites.Site", on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="site_configurations")
    content_locale = models.CharField(max_length=35)
    visible = models.BooleanField(default=False)
    canonical_path = models.CharField(max_length=1000)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("site", "category", "content_locale"), name="classifier_site_category_locale_unique"
            ),
            models.UniqueConstraint(fields=("site", "canonical_path"), name="classifier_site_canonical_unique"),
        ]
