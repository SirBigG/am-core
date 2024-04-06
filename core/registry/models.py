from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel
from transliterate import slugify

from core.classifier.models import Country
from core.services.models import MetaData


class Company(models.Model):
    name = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255, blank=True, null=True)
    code = models.IntegerField(blank=True, null=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"


class VarietyCategory(MPTTModel):
    """Model realize tree structure for categories."""

    slug = models.CharField(max_length=255, unique=True, verbose_name=_("transliteration value"))
    title = models.CharField(max_length=255, verbose_name=_("category title"))
    parent = TreeForeignKey(
        "self",
        blank=True,
        null=True,
        related_name="children",
        db_index=True,
        on_delete=models.CASCADE,
        verbose_name=_("category parent"),
    )
    meta = models.OneToOneField(
        MetaData,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("category meta data"),
        related_name="category-meta-data+",
    )
    absolute_url = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("category absolute url"))

    class MPTTMeta:
        order_insertion_by = ["slug"]
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title.lower(), get_language())
        if not self.absolute_url:
            _url = "/registry/"
            for _slug in self.get_ancestors(include_self=True).values_list("slug", flat=True).order_by("level"):
                _url += f"{_slug}/"
            self.absolute_url = _url
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        if self.absolute_url:
            return self.absolute_url
        _url = "/registry/"
        for _slug in self.get_ancestors(include_self=True).values_list("slug", flat=True).order_by("level"):
            _url += f"{_slug}/"
        self.absolute_url = _url
        self.save()
        return self.absolute_url


class Variety(models.Model):
    title = models.CharField(max_length=255)
    title_original = models.CharField(max_length=255, blank=True, null=True)
    application_number = models.CharField(max_length=255, blank=True, null=True)
    registration_year = models.IntegerField(blank=True, null=True)
    unregister_year = models.IntegerField(blank=True, null=True)
    unregister_date = models.DateField(blank=True, null=True)
    recommended_zone = models.CharField(max_length=50, blank=True, null=True)
    direction_of_use = models.CharField(max_length=50, blank=True, null=True)
    ripeness_group = models.CharField(max_length=50, blank=True, null=True)
    quality = models.CharField(max_length=50, blank=True, null=True)
    registration_country = models.ForeignKey(Country, on_delete=models.SET_NULL, blank=True, null=True)
    original_country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, blank=True, null=True, related_name="original_country"
    )
    applicant = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True, related_name="applicant")
    applicant2 = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True, related_name="applicant2")
    owner = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True, related_name="owner")
    owner2 = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True, related_name="owner2")
    breeder = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True, related_name="breeder")
    breeder2 = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True, related_name="breeder2")
    excluded = models.BooleanField(default=False)
    slug = models.CharField(max_length=255)
    category = models.ForeignKey(VarietyCategory, on_delete=models.SET_NULL, blank=True, null=True)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    publication = models.ForeignKey("posts.Post", on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Variety"
        verbose_name_plural = "Varieties"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title.lower(), get_language())
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        if self.publication_id:
            return self.publication.get_absolute_url()
        return
