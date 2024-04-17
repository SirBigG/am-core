from datetime import datetime

from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel
from transliterate import slugify

from core.classifier.models import Country
from core.registry.parser_row_types import ActiveRegistryItem, InactiveRegistryItem
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

    @classmethod
    def save_company_from_row(cls, row):
        code = row[2]
        if Company.objects.filter(code=code).exists():
            return
        company = Company(
            name=row[3],
            original_name=row[4],
            code=code,
            country=Country.objects.filter(short_slug=row[5].lower()).first(),
        )
        company.save()
        return company


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

    @classmethod
    def save_active_variety_from_row(cls, row: list):
        item = ActiveRegistryItem._make(row)
        base_category_title = item.base_category_title
        # Check if category already exists
        slug = slugify(base_category_title, get_language())
        base_category = VarietyCategory.objects.filter(slug=slug).first()
        if base_category is None:
            base_category = VarietyCategory.objects.create(title=base_category_title)
            base_category.save()
        base_category_id = base_category.id
        children_category_title = item.child_category_title
        # Check if category already exists
        slug = slugify(children_category_title, get_language())
        children_category = VarietyCategory.objects.filter(slug=slug).first()
        if children_category is None:
            children_category = VarietyCategory.objects.create(
                title=children_category_title, parent_id=base_category_id
            )
            children_category.save()
        children_category_id = children_category.id
        title = item.title
        if Variety.objects.filter(title=title, category_id=children_category_id).exists():
            return
        registration_country = item.registration_country
        if registration_country:
            registration_country = Country.objects.filter(short_slug=registration_country.lower()).first()
        original_country = item.original_country
        if original_country:
            original_country = Country.objects.filter(short_slug=original_country.lower()).first()
        variety = Variety(
            title=title,
            title_original=item.title_original,
            application_number=item.application_number,
            registration_year=item.registration_year,
            recommended_zone=item.recommended_zone,
            direction_of_use=item.direction_of_use,
            ripeness_group=item.ripeness_group,
            quality=item.quality,
            registration_country_id=registration_country,
            original_country_id=original_country,
            applicant=Company.objects.filter(code=item.applicant).first() if item.applicant else None,
            applicant2=Company.objects.filter(code=item.applicant2).first() if item.applicant2 else None,
            owner=Company.objects.filter(code=item.owner).first() if item.owner else None,
            owner2=Company.objects.filter(code=item.owner2).first() if item.owner2 else None,
            breeder=Company.objects.filter(code=item.breeder).first() if item.breeder else None,
            category_id=children_category_id,
        )
        variety.save()

    @classmethod
    def save_inactive_variety_from_row(cls, row: list):
        item = InactiveRegistryItem._make(row)
        end_date = item.end_date
        end_date_year = None
        if end_date:
            # parse end date by format dd.mm.yyyy
            end_date = datetime.strptime(end_date, "%d.%m.%Y").date()
            end_date_year = end_date.year
        base_category_title = item.base_category_title
        # Check if category already exists
        slug = slugify(base_category_title, get_language())
        base_category = VarietyCategory.objects.filter(slug=slug).first()
        if base_category is None:
            base_category = VarietyCategory.objects.create(title=base_category_title)
            base_category.save()
        base_category_id = base_category.id
        children_category_title = item.child_category_title
        # Check if category already exists
        slug = slugify(children_category_title, get_language())
        children_category = VarietyCategory.objects.filter(slug=slug).first()
        if children_category is None:
            children_category = VarietyCategory.objects.create(
                title=children_category_title, parent_id=base_category_id
            )
            children_category.save()

        children_category_id = children_category.id
        title = item.title
        if Variety.objects.filter(title=title, category_id=children_category_id).exists():
            Variety.objects.filter(title=title, category_id=children_category_id).update(
                unregister_date=end_date, unregister_year=end_date_year, excluded=True
            )
            return
        registration_country = item.registration_country
        if registration_country:
            registration_country = Country.objects.filter(short_slug=registration_country.lower()).first()
        original_country = item.original_country
        if original_country:
            original_country = Country.objects.filter(short_slug=original_country.lower()).first()
        variety = Variety(
            title=title,
            title_original=item.title_original,
            application_number=item.application_number,
            registration_year=item.registration_year,
            recommended_zone=item.recommended_zone,
            direction_of_use=item.direction_of_use,
            ripeness_group=item.ripeness_group,
            quality=item.quality,
            registration_country_id=registration_country,
            original_country_id=original_country,
            applicant_id=Company.objects.filter(code=item.applicant).first() if item.applicant else None,
            applicant2_id=Company.objects.filter(code=item.applicant2).first() if item.applicant2 else None,
            owner_id=Company.objects.filter(code=item.owner).first() if item.owner else None,
            owner2_id=Company.objects.filter(code=item.owner2).first() if item.owner2 else None,
            breeder_id=Company.objects.filter(code=item.breeder).first() if item.breeder else None,
            category_id=children_category_id,
            unregister_date=end_date,
            unregister_year=end_date_year,
            excluded=True,
        )
        variety.save()
