from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import models
from django.utils.translation import gettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey
from PIL import Image

from core.services.models import MetaData


class Country(models.Model):
    """Model for country."""

    slug = models.CharField(max_length=250, verbose_name=_("transliteration value"))
    short_slug = models.CharField(max_length=5, verbose_name=_("short slug"))
    value = models.CharField(max_length=250, unique=True, verbose_name=_("country value"))

    class Meta:
        db_table = "country"
        verbose_name = _("country")
        verbose_name_plural = _("countries")
        ordering = ["value"]

    def __str__(self):
        return self.value


class Region(models.Model):
    """Model for region."""

    slug = models.CharField(max_length=250, verbose_name=_("transliteration value"))
    value = models.CharField(max_length=250, unique=True, verbose_name=_("region value"))
    country = models.ForeignKey(
        Country, on_delete=models.CASCADE, related_name="region_country", verbose_name=_("region country")
    )

    class Meta:
        db_table = "region"
        verbose_name = _("region")
        verbose_name_plural = _("region")

    def __str__(self):
        return self.value


class Area(models.Model):
    """Model for area."""

    slug = models.CharField(max_length=250, verbose_name=_("transliteration value"))
    value = models.CharField(max_length=250, verbose_name=_("area value"))
    region = models.ForeignKey(
        Region, on_delete=models.CASCADE, related_name="area_region", verbose_name=_("area region")
    )

    class Meta:
        db_table = "area"
        verbose_name = _("area")
        verbose_name_plural = _("area")

    def __str__(self):
        return self.value


class Location(models.Model):
    """Model for locations."""

    slug = models.CharField(max_length=250, verbose_name=_("transliteration value"))
    value = models.CharField(max_length=250, verbose_name=_("location value"))
    country = models.ForeignKey(Country, on_delete=models.CASCADE, verbose_name=_("country"))
    region = models.ForeignKey(Region, on_delete=models.CASCADE, verbose_name=_("region"))
    area = models.ForeignKey(Area, on_delete=models.CASCADE, verbose_name=_("area"))
    longitude = models.FloatField(verbose_name=_("location longitude"), blank=True, null=True)
    latitude = models.FloatField(verbose_name=_("location latitude"), blank=True, null=True)

    class Meta:
        db_table = "location"
        verbose_name = _("location")
        verbose_name_plural = _("locations")

    def __str__(self):
        return f"{self.value} ({str(self.region)} {str(self.area)})"


class CategoryPresentationMode(models.TextChoices):
    CATALOG = "catalog", _("catalog")
    GUIDE_HUB = "guide_hub", _("guide hub")


class Category(MPTTModel):
    """Model realize tree structure for categories."""

    slug = models.CharField(max_length=250, unique=True, verbose_name=_("transliteration value"))
    value = models.CharField(max_length=250, verbose_name=_("category value"))
    icon = models.CharField(max_length=250, blank=True, null=True, verbose_name=_("category icon"))
    parent = TreeForeignKey(
        "self",
        blank=True,
        null=True,
        related_name="children",
        db_index=True,
        on_delete=models.CASCADE,
        verbose_name=_("category parent"),
    )
    is_for_user = models.BooleanField(default=False, verbose_name=_("user relation for post category"))
    is_diary_species_parent = models.BooleanField(
        default=False,
        verbose_name=_("diary species parent"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("for feel on off"))
    presentation_mode = models.CharField(
        max_length=20,
        choices=CategoryPresentationMode,
        default=CategoryPresentationMode.CATALOG,
        verbose_name=_("presentation mode"),
        help_text=_("Default presentation; future site configuration may override this value."),
    )

    absolute_url = models.CharField(max_length=1000, blank=True, null=True, verbose_name=_("absolute url"))

    image = models.ImageField(upload_to="categories", blank=True, null=True)

    meta = models.OneToOneField(
        MetaData,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("category meta data"),
        related_name="category-meta-data+",
    )

    class MPTTMeta:
        order_insertion_by = ["slug"]
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")

    def __str__(self):
        return self.value

    def get_absolute_url(self):
        return "/%s/" % "/".join(self.get_ancestors(include_self=True).values_list("slug", flat=True)[1:])

    def save(self, *args, **kwargs):
        if self.image:
            HEIGHT = 200
            WIDTH = 300
            img = Image.open(BytesIO(self.image.read()))
            hsize = int(float(img.size[1]) * float(WIDTH) / float(img.size[0]))
            if hsize >= HEIGHT:
                img = img.resize((WIDTH, hsize), Image.LANCZOS)
                delta = hsize - HEIGHT if hsize > HEIGHT else 0
                img = img.crop((0, delta / 2, WIDTH, hsize - (delta / 2)))
            elif hsize < HEIGHT:
                wsize = int(float(img.size[0]) * float(HEIGHT) / float(img.size[1]))
                img = img.resize((wsize, HEIGHT), Image.LANCZOS)
                delta = wsize - WIDTH if wsize > WIDTH else 0
                img = img.crop((delta / 2, 0, wsize - (delta / 2), HEIGHT))
            else:
                # If not height resize with auto height
                img = img.resize((WIDTH, hsize), Image.LANCZOS)
            output = BytesIO()
            img.save(output, "JPEG")
            self.image = File(output, name=self.image.name)
        super().save(*args, **kwargs)
        Category.objects.filter(pk=self.pk).update(absolute_url=self.get_absolute_url())


class CategoryAIProfile(models.Model):
    """Private plant-care knowledge used as AI context for diary
    recommendations."""

    STATUS_DRAFT = "draft"
    STATUS_READY = "ready"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_DRAFT, _("Draft")),
        (STATUS_READY, _("Ready")),
        (STATUS_ARCHIVED, _("Archived")),
    ]

    category = models.OneToOneField(
        Category,
        on_delete=models.CASCADE,
        related_name="ai_profile",
        verbose_name=_("category"),
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("AI profile title"),
        help_text=_("Optional readable title, for example: Basil (Ocimum basilicum)."),
    )
    content = models.TextField(
        blank=True,
        verbose_name=_("AI knowledge content"),
        help_text=_("Structured plain text or Markdown used as private AI context. This text is not published."),
    )
    recommendation_rules = models.TextField(
        blank=True,
        verbose_name=_("AI recommendation rules"),
        help_text=_(
            "Structured rules for risks, triggers, confidence, and recommendations used as private AI context."
        ),
    )
    sources = models.TextField(
        blank=True,
        verbose_name=_("sources"),
        help_text=_("Optional links, books, notes, or source references for this knowledge profile."),
    )
    internal_notes = models.TextField(
        blank=True,
        verbose_name=_("internal notes"),
        help_text=_("Optional team-only notes. Not intended for AI prompts by default."),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name=_("status"),
    )
    is_ai_enabled = models.BooleanField(
        default=True,
        verbose_name=_("use for AI recommendations"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_category_ai_profiles",
        verbose_name=_("updated by"),
    )
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("updated"))

    class Meta:
        db_table = "classifier_category_ai_profile"
        verbose_name = _("AI documentation")
        verbose_name_plural = _("AI documentation")
        ordering = ["category__value"]

    def __str__(self):
        return self.title or f"{self.category} AI documentation"


def _validate_hub_target(category_id, target_id, *, include_self=False):
    """Explicit references may cross taxonomy branches without moving content.

    Section navigation cannot point back to the hub or include it
    through an ancestor catalog. Guide sources are direct collections
    and may use self.
    """
    if include_self:
        return
    bounds = Category.objects.filter(pk=category_id).values("tree_id", "lft", "rght").first()
    if (
        bounds
        and Category.objects.filter(
            pk=target_id,
            tree_id=bounds["tree_id"],
            lft__lte=bounds["lft"],
            rght__gte=bounds["rght"],
        ).exists()
    ):
        raise ValidationError(_("Choose a section category other than this hub or its ancestors."))


class CategoryHub(models.Model):
    """Presentation configuration referencing the existing taxonomy."""

    category = models.OneToOneField(Category, on_delete=models.CASCADE, related_name="crop_hub")
    is_active = models.BooleanField(default=False, verbose_name=_("active"))
    description = models.TextField(blank=True, verbose_name=_("short introduction"))
    guide_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="guide_source_for_hubs",
        help_text=_("Optional existing guide source. Blank uses guide sections on the hub category."),
    )
    site = models.ForeignKey(
        "sites.Site",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        help_text=_("Optional display restriction. Blank uses this hub on every site owning this database."),
    )
    locale = models.CharField(
        max_length=20,
        blank=True,
        help_text=_("Optional language code, for example uk. Blank uses this hub in every language."),
    )
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("category hub")
        verbose_name_plural = _("category hubs")
        ordering = ("category__value",)

    def __str__(self):
        return str(self.category)

    def clean(self):
        super().clean()
        self.locale = self.locale.strip().lower()
        if self.locale and self.locale not in dict(settings.LANGUAGES):
            raise ValidationError({"locale": _("Select a language enabled for this application.")})
        if self.category_id and self.guide_category_id:
            try:
                _validate_hub_target(self.category_id, self.guide_category_id, include_self=True)
            except ValidationError as exc:
                raise ValidationError({"guide_category": exc.messages}) from exc


class CategoryHubSection(models.Model):
    class Role(models.TextChoices):
        VARIETIES = "varieties", _("varieties")
        DISEASES = "diseases", _("diseases")
        PESTS = "pests", _("pests")
        GROWING = "growing", _("growing and care")
        ADDITIONAL = "additional", _("additional section")

    hub = models.ForeignKey(CategoryHub, on_delete=models.CASCADE, related_name="sections")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="hub_sections")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ADDITIONAL)
    title = models.CharField(max_length=250, blank=True, verbose_name=_("label override"))
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("hub section")
        verbose_name_plural = _("hub sections")
        ordering = ("sort_order", "pk")
        constraints = [
            models.UniqueConstraint(fields=("hub", "category"), name="unique_hub_section_category"),
            models.UniqueConstraint(
                fields=("hub", "role"),
                condition=~models.Q(role="additional"),
                name="unique_hub_primary_role",
            ),
        ]

    def __str__(self):
        return self.title or str(self.category)

    def clean(self):
        super().clean()
        hub = getattr(self, "hub", None)
        if self.category_id and hub is not None and hub.category_id:
            try:
                _validate_hub_target(hub.category_id, self.category_id)
            except ValidationError as exc:
                raise ValidationError({"category": exc.messages}) from exc
