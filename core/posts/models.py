import os
import random
import string
from io import BytesIO

from ckeditor.fields import RichTextField
from comment.models import Comment
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.files import File
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from PIL import Image
from taggit.managers import TaggableManager
from transliterate import slugify

from core.classifier.models import Category, Country
from core.pro_auth.models import User
from core.services.models import MetaData

WORK_STATUS = (
    (1, _("Translate")),
    (2, _("Publish")),
)


class CategoryAttributeFieldType(models.TextChoices):
    SELECT = "select", _("select")
    MULTISELECT = "multiselect", _("multiple select")
    INTEGER = "integer", _("integer")
    DECIMAL = "decimal", _("decimal")
    RANGE = "range", _("range")
    BOOLEAN = "boolean", _("boolean")


class PostQuerySet(models.QuerySet):
    def select_objects(self):
        return (
            self.select_related("country")
            .prefetch_related("photo")
            .select_related("rubric")
            .select_related("rubric__parent")
            .select_related("rubric__meta")
        )

    def active(self):
        return self.filter(status=True)


class Post(models.Model):
    """Posts model."""

    title = models.CharField(max_length=500, verbose_name=_("post title"))
    text = RichTextField(verbose_name=_("post text"))
    slug = models.CharField(max_length=250, unique=True, verbose_name=_("transliteration value"))
    work_status = models.IntegerField(
        choices=WORK_STATUS, default=None, blank=True, null=True, verbose_name=_("status of author work")
    )
    author = models.CharField(max_length=250, blank=True, null=True, verbose_name=_("post author"))
    source = models.CharField(max_length=250, blank=True, null=True, verbose_name=_("post source"))
    sources = RichTextField(blank=True, null=True, verbose_name=_("post sources"))

    publisher = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("post publisher"))
    publish_date = models.DateTimeField(_("date of publish"), default=timezone.now)
    update_date = models.DateTimeField(_("date of update"), default=timezone.now)

    hits = models.IntegerField(default=0, verbose_name=_("count of views"))

    status = models.BooleanField(default=True, verbose_name=_("post status"))

    rubric = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name=_("post category"))

    meta_description = models.CharField(max_length=250, blank=True, null=True, verbose_name=_("meta description"))

    meta = models.OneToOneField(
        MetaData,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("post meta data"),
        related_name="post-meta-data+",
    )

    country = models.ForeignKey(
        Country, on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("origin country")
    )

    absolute_url = models.CharField(max_length=512, default="")

    tags = TaggableManager()
    category_attributes = models.JSONField(blank=True, default=dict, verbose_name=_("category attributes"))

    comments = GenericRelation(Comment)

    text_search = SearchVectorField(null=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        db_table = "post"
        verbose_name = _("Post")
        verbose_name_plural = _("Posts")
        ordering = ["-publish_date"]
        indexes = [GinIndex(fields=["text_search"])]

    def __str__(self):
        return f"{self.title} | {self.rubric}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title.lower(), get_language())
            if self.__class__.objects.filter(slug=self.slug).first():
                self.slug = self.slug + "".join(random.choice(string.ascii_lowercase) for _ in range(4))  # nosec
        # always upgrade absolute url on save
        if self.pk and self.rubric_id and self.rubric.parent_id:
            self.absolute_url = reverse(
                "post-detail",
                args=(
                    self.rubric.parent.slug,
                    self.rubric.slug,
                    self.slug,
                    self.pk,
                ),
            )
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        if self.absolute_url:
            return self.absolute_url
        # Set absolute url value for quick get
        # Upgrade absolute url if not set
        self.absolute_url = reverse(
            "post-detail",
            args=(
                self.rubric.parent.slug,
                self.rubric.slug,
                self.slug,
                self.pk,
            ),
        )
        self.save()
        return self.absolute_url


class CategoryAttributeGroup(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="attribute_groups",
        verbose_name=_("category"),
    )
    title = models.CharField(max_length=250, verbose_name=_("title"))
    description = models.TextField(blank=True, verbose_name=_("description"))
    is_active = models.BooleanField(default=True, verbose_name=_("active"))
    sort_order = models.PositiveIntegerField(default=0, verbose_name=_("sort order"))

    class Meta:
        db_table = "category_attribute_group"
        verbose_name = _("Category attribute group")
        verbose_name_plural = _("Category attribute groups")
        ordering = ("category__value", "sort_order", "title")

    def __str__(self):
        return f"{self.category}: {self.title}"


class CategoryAttributeField(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="attribute_fields",
        verbose_name=_("category"),
    )
    group = models.ForeignKey(
        CategoryAttributeGroup,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="fields",
        verbose_name=_("group"),
    )
    key = models.SlugField(max_length=120, verbose_name=_("key"))
    label = models.CharField(max_length=250, verbose_name=_("label"))
    field_type = models.CharField(
        max_length=20,
        choices=CategoryAttributeFieldType,
        verbose_name=_("field type"),
    )
    help_text = models.TextField(blank=True, verbose_name=_("help text"))
    unit = models.CharField(max_length=50, blank=True, verbose_name=_("unit"))
    decimal_places = models.PositiveSmallIntegerField(default=0, verbose_name=_("decimal places"))
    min_value = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name=_("minimum value"),
    )
    max_value = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name=_("maximum value"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("active"))
    is_required = models.BooleanField(default=False, verbose_name=_("required"))
    is_filterable = models.BooleanField(default=True, verbose_name=_("filterable"))
    is_public = models.BooleanField(default=True, verbose_name=_("public"))
    sort_order = models.PositiveIntegerField(default=0, verbose_name=_("sort order"))

    class Meta:
        db_table = "category_attribute_field"
        verbose_name = _("Category attribute field")
        verbose_name_plural = _("Category attribute fields")
        ordering = ("category__value", "group__sort_order", "sort_order", "label")
        constraints = [
            models.UniqueConstraint(fields=("category", "key"), name="unique_category_attribute_field_key"),
        ]

    def __str__(self):
        return f"{self.category}: {self.label}"


class CategoryAttributeChoice(models.Model):
    field = models.ForeignKey(
        CategoryAttributeField,
        on_delete=models.CASCADE,
        related_name="choices",
        verbose_name=_("field"),
    )
    value = models.SlugField(max_length=120, verbose_name=_("value"))
    label = models.CharField(max_length=250, verbose_name=_("label"))
    is_active = models.BooleanField(default=True, verbose_name=_("active"))
    is_public = models.BooleanField(default=True, verbose_name=_("public"))
    sort_order = models.PositiveIntegerField(default=0, verbose_name=_("sort order"))

    class Meta:
        db_table = "category_attribute_choice"
        verbose_name = _("Category attribute choice")
        verbose_name_plural = _("Category attribute choices")
        ordering = ("field__sort_order", "sort_order", "label")
        constraints = [
            models.UniqueConstraint(fields=("field", "value"), name="unique_category_attribute_choice_value"),
        ]

    def __str__(self):
        return f"{self.field}: {self.label}"


class PostAttributeValue(models.Model):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="attribute_values",
        verbose_name=_("post"),
    )
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name=_("category"))
    field = models.ForeignKey(
        CategoryAttributeField,
        on_delete=models.CASCADE,
        related_name="post_values",
        verbose_name=_("field"),
    )
    choice = models.ForeignKey(
        CategoryAttributeChoice,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="post_values",
        verbose_name=_("choice"),
    )
    value_text = models.CharField(max_length=250, blank=True, verbose_name=_("text value"))
    value_number = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name=_("number value"),
    )
    value_number_min = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name=_("minimum number value"),
    )
    value_number_max = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name=_("maximum number value"),
    )
    value_boolean = models.BooleanField(blank=True, null=True, verbose_name=_("boolean value"))

    class Meta:
        db_table = "post_attribute_value"
        verbose_name = _("Post attribute value")
        verbose_name_plural = _("Post attribute values")
        indexes = [
            models.Index(fields=("category", "field")),
            models.Index(fields=("post", "field")),
            models.Index(fields=("field", "choice")),
            models.Index(fields=("field", "value_number_min", "value_number_max")),
        ]

    def __str__(self):
        return f"{self.post_id}: {self.field}"


class Photo(models.Model):
    """Post photos model."""

    image = models.ImageField(upload_to="images", verbose_name=_("image"))
    description = models.CharField(max_length=500, blank=True, null=True, verbose_name=_("photo describing"))
    post = models.ForeignKey(Post, on_delete=models.CASCADE, verbose_name=_("post of photo"), related_name="photo")
    author = models.CharField(max_length=150, blank=True, null=True, verbose_name=_("author of photo"))
    source = models.CharField(max_length=150, blank=True, null=True, verbose_name=_("photo source"))

    class Meta:
        db_table = "photo"
        verbose_name = _("Photo")
        verbose_name_plural = _("Photos")

    def __str__(self):
        return str(self.id)

    def save(self, *args, **kwargs):
        """Cut image before save."""
        if self.image:
            im = Image.open(BytesIO(self.image.read()))
            if im.mode != "RGB":
                im = im.convert("RGB")
            im.thumbnail((1000, 800), Image.LANCZOS)
            output = BytesIO()
            im.save(output, format="webp", quality=85)
            self.image = File(output, self.image.name.split(".")[0] + ".webp")
        super().save(*args, **kwargs)

    def thumbnail(self, width=300, height=200):
        if not self.image:
            return None

        try:
            image = Image.open(self.image.path)
        except FileNotFoundError:
            return None

        thumb_dir = os.path.join(settings.MEDIA_ROOT, "images", "thumb", str(width))
        os.makedirs(thumb_dir, exist_ok=True)

        thumb_name = os.path.basename(self.image.name)
        thumb_path = os.path.join(thumb_dir, thumb_name)
        image.thumbnail((width, height), Image.LANCZOS)
        image.save(thumb_path)

        return f"{settings.MEDIA_URL}images/thumb/{width}/{thumb_name}"

    def delete(self, *args, **kwargs):
        path = self.image.path if self.image else None
        super().delete(*args, **kwargs)
        if path and os.path.exists(path):
            os.remove(path)


class ParsedMap(models.Model):
    host = models.CharField(max_length=255)
    link = models.CharField(max_length=500)
    map = models.TextField()
    root = models.CharField(max_length=255)
    type = models.IntegerField()

    def __str__(self):
        return f"{self.host} {self.link}"


class UsefulStatistic(models.Model):
    fingerprint = models.CharField(max_length=255, verbose_name=_("fingerprint"))
    post_id = models.IntegerField(verbose_name=_("post identifier"))
    user_id = models.IntegerField(blank=True, null=True, verbose_name=_("user identifier"))
    is_useful = models.BooleanField(_("is useful post"))
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("created"))

    def __str__(self):
        return f"{self.fingerprint} - {self.post_id}"


class SearchStatistic(models.Model):
    fingerprint = models.CharField(max_length=255, verbose_name=_("fingerprint"))
    search_phrase = models.CharField(max_length=255, verbose_name=_("fingerprint"))
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("created"))

    def __str__(self):
        return f"{self.fingerprint} - {self.search_phrase[:40]}"
