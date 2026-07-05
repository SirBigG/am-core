from datetime import date, datetime

from django.conf import settings
from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel
from transliterate import slugify

from core.classifier.models import Country
from core.registry.parser_row_types import (
    ActiveRegistryItem,
    InactiveRegistryItem,
    normalize_active_registry_row,
    normalize_inactive_registry_row,
)
from core.services.models import MetaData


def _get_or_create_registry_category(title, parent_id=None):
    slug = slugify(title, get_language())
    category = VarietyCategory.objects.filter(slug=slug).first()
    if category is None:
        category = VarietyCategory.objects.create(title=title, parent_id=parent_id)
    return category


def _parse_registry_date(value):
    if not value:
        return None, None
    if isinstance(value, datetime):
        return value.date(), value.year
    if isinstance(value, date):
        return value, value.year
    try:
        value = datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        value = datetime.strptime(value, "%Y-%m-%d").date()
    return value, value.year


def _variety_defaults_from_item(item, children_category_id, *, excluded=False, end_date=None, end_date_year=None):
    registration_country_slug = item.registration_country
    registration_country = None
    if registration_country_slug:
        registration_country = Country.objects.filter(short_slug=registration_country_slug.lower()).first()
    original_country_slug = item.original_country
    original_country = None
    if original_country_slug:
        original_country = Country.objects.filter(short_slug=original_country_slug.lower()).first()
    return {
        "title_original": item.title_original,
        "application_number": item.application_number,
        "registration_year": item.registration_year,
        "recommended_zone": item.recommended_zone,
        "direction_of_use": item.direction_of_use,
        "ripeness_group": item.ripeness_group,
        "quality": item.quality,
        "registration_country": registration_country,
        "original_country": original_country,
        "applicant": Company.objects.filter(code=item.applicant).first() if item.applicant else None,
        "applicant2": Company.objects.filter(code=item.applicant2).first() if item.applicant2 else None,
        "owner": Company.objects.filter(code=item.owner).first() if item.owner else None,
        "owner2": Company.objects.filter(code=item.owner2).first() if item.owner2 else None,
        "breeder": Company.objects.filter(code=item.breeder).first() if item.breeder else None,
        "category_id": children_category_id,
        "unregister_date": end_date,
        "unregister_year": end_date_year,
        "excluded": excluded,
    }


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

    @classmethod
    def save_company_from_row(cls, row):
        code = row[2]
        if not code:
            return
        country_slug = row[5]
        country = Country.objects.filter(short_slug=country_slug.lower()).first() if country_slug else None
        company, created = Company.objects.update_or_create(
            code=code,
            defaults={
                "name": row[3],
                "original_name": row[4],
                "country": country,
            },
        )
        if created:
            return company
        return company


class RegistryImportJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        SUCCEEDED = "succeeded", _("Succeeded")
        FAILED = "failed", _("Failed")

    source_file = models.FileField(upload_to="registry/imports")
    original_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    summary = models.JSONField(blank=True, null=True)
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="registry_import_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.original_filename} ({self.status})"


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
        super().save(*args, **kwargs)
        if not self.absolute_url:
            _url = "/registry/"
            for _slug in self.get_ancestors(include_self=True).values_list("slug", flat=True).order_by("level"):
                _url += f"{_slug}/"
            self.absolute_url = _url
            self.save()

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

    @classmethod
    def save_active_variety_from_row(cls, row: list):
        row = normalize_active_registry_row(row)
        item = ActiveRegistryItem._make(row)
        base_category_title = item.base_category_title
        base_category = _get_or_create_registry_category(base_category_title)
        base_category_id = base_category.id
        children_category_title = item.child_category_title
        children_category = _get_or_create_registry_category(children_category_title, parent_id=base_category_id)
        children_category_id = children_category.id
        title = item.title
        variety, _ = Variety.objects.update_or_create(
            title=title,
            category_id=children_category_id,
            defaults=_variety_defaults_from_item(item, children_category_id),
        )
        return variety

    @classmethod
    def save_inactive_variety_from_row(cls, row: list):
        row = normalize_inactive_registry_row(row)
        item = InactiveRegistryItem._make(row)
        end_date, end_date_year = _parse_registry_date(item.end_date)
        base_category_title = item.base_category_title
        base_category = _get_or_create_registry_category(base_category_title)
        base_category_id = base_category.id
        children_category_title = item.child_category_title
        children_category = _get_or_create_registry_category(children_category_title, parent_id=base_category_id)

        children_category_id = children_category.id
        title = item.title
        variety, _ = Variety.objects.update_or_create(
            title=title,
            category_id=children_category_id,
            defaults=_variety_defaults_from_item(
                item,
                children_category_id,
                excluded=True,
                end_date=end_date,
                end_date_year=end_date_year,
            ),
        )
        return variety
