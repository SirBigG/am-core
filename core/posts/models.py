import random
import string
from io import BytesIO

from ckeditor.fields import RichTextField
from comment.models import Comment
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
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
    sources = ArrayField(
        models.CharField(max_length=250),
        blank=True,
        null=True,
        verbose_name=_("post sources"),
        help_text=_("Enter sources separated by commas"),
    )

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
        if self.pk:
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
