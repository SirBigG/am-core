from PIL import Image
from io import BytesIO
from pathlib import Path
import hashlib
import random
import string

from django.db import models
from django.utils.translation import get_language, gettext_lazy as _
from django.utils import timezone
from django.urls import reverse
from django.core.files import File
from django.conf import settings
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.contenttypes.fields import GenericRelation

from comment.models import Comment

from core.pro_auth.models import User

from core.classifier.models import Category, Country
from core.services.models import MetaData

from ckeditor.fields import RichTextField

from transliterate import slugify

from taggit.managers import TaggableManager


WORK_STATUS = (
    (1, _('Translate')),
    (2, _('Publish')),
)


class PostQuerySet(models.QuerySet):
    def select_objects(self):
        return self.select_related('country').prefetch_related('photo').select_related(
            'rubric').select_related('rubric__parent').select_related('rubric__meta')

    def active(self):
        return self.filter(status=True)


class Post(models.Model):
    """Posts model."""
    title = models.CharField(max_length=500, verbose_name=_('post title'))
    text = RichTextField(verbose_name=_('post text'))
    slug = models.CharField(max_length=250, unique=True, verbose_name=_('transliteration value'))
    work_status = models.IntegerField(choices=WORK_STATUS, default=None,
                                      blank=True, null=True,
                                      verbose_name=_('status of author work'))
    author = models.CharField(max_length=250, blank=True, null=True, verbose_name=_('post author'))
    source = models.CharField(max_length=250, blank=True, null=True, verbose_name=_('post source'))

    publisher = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('post publisher'))
    publish_date = models.DateTimeField(_('date of publish'), default=timezone.now)

    hits = models.IntegerField(default=0, verbose_name=_('count of views'))

    status = models.BooleanField(default=1, verbose_name=_('post status'))

    rubric = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name=_('post category'))

    meta_description = models.CharField(max_length=250, blank=True, null=True, verbose_name=_('meta description'))

    meta = models.OneToOneField(MetaData, on_delete=models.CASCADE, blank=True, null=True,
                                verbose_name=_('post meta data'), related_name="post-meta-data+")

    country = models.ForeignKey(Country, on_delete=models.CASCADE, blank=True, null=True,
                                verbose_name=_('post country'))

    absolute_url = models.CharField(max_length=512, default="")

    tags = TaggableManager()

    comments = GenericRelation(Comment)

    text_search = SearchVectorField(null=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        db_table = 'post'
        verbose_name = _('Post')
        verbose_name_plural = _('Posts')
        ordering = ['-publish_date']
        indexes = [GinIndex(fields=["text_search"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title.lower(), get_language()[:2])
            if self.__class__.objects.filter(slug=self.slug).first():
                self.slug = self.slug + ''.join(random.choice(string.ascii_lowercase) for _ in range(4))
        # always upgrade absolute url on save
        if self.pk:
            self.absolute_url = reverse('post-detail', args=(self.rubric.parent.slug, self.rubric.slug,
                                                             self.slug, self.pk,))
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        if self.absolute_url:
            return self.absolute_url
        # Set absolute url value for quick get
        # Upgrade absolute url if not set
        self.absolute_url = reverse('post-detail', args=(self.rubric.parent.slug, self.rubric.slug,
                                                         self.slug, self.pk,))
        self.save()
        return self.absolute_url


class Photo(models.Model):
    """Post photos model."""
    image = models.ImageField(upload_to='images', verbose_name=_('image'))
    description = models.CharField(max_length=500, blank=True, null=True, verbose_name=_('photo describing'))
    post = models.ForeignKey(Post, on_delete=models.CASCADE, verbose_name=_('post of photo'), related_name='photo')
    author = models.CharField(max_length=150, blank=True, null=True, verbose_name=_('author of photo'))
    source = models.CharField(max_length=150, blank=True, null=True, verbose_name=_('photo source'))

    class Meta:
        db_table = 'photo'
        verbose_name = _('Photo')
        verbose_name_plural = _('Photos')

    def __str__(self):
        return str(self.id)

    def _get_thumbnail_path(self, width):
        """Return thumbnail path with dirs created."""
        path_dict = self.image.path.split('/')
        path = Path('%s/thumb/' % ('/'.join(path_dict[:-1])))
        if path.is_dir() is False:
            path.mkdir()
        path = Path(('%s/%s/' % (str(path), width)).replace('//', '/'))
        if path.is_dir() is False:
            path.mkdir()
        return '%s/%s' % (str(path), path_dict[-1].split('.')[0] + '.webp')

    def thumbnail(self, width=300, height=None):
        """
           Create thumbnail if not exists for current image.
           Returns: url to thumbnail.
        """
        if self.image:
            thumb_path = Path(self._get_thumbnail_path(width))
            if thumb_path.is_file() is False:
                try:
                    im = Image.open(self.image.path)
                except FileNotFoundError:
                    return
                if height is None:
                    height = int((float(im.size[1]) * float(width / float(im.size[0]))))
                im = im.resize((width, height), Image.ANTIALIAS)
                im.save(thumb_path, format='webp', quality=80)
            return ('%s%s' % (settings.MEDIA_URL, str(thumb_path).replace(settings.MEDIA_ROOT, ""))).replace('//', '/')

    def save(self, *args, **kwargs):
        """Cut image before save."""
        if self.image:
            im = Image.open(BytesIO(self.image.read()))
            if im.mode != 'RGB':
                im = im.convert('RGB')
            im.thumbnail((1000, 800), Image.ANTIALIAS)
            output = BytesIO()
            im.save(output, format='JPEG', quality=85)
            self.image = File(output, self.image.name)
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Delete file of image after object deleting."""
        path = self.image.path
        super().delete(using=None, keep_parents=False)
        import os
        os.remove(path)


class ParsedMap(models.Model):
    host = models.CharField(max_length=255)
    link = models.CharField(max_length=500)
    map = models.TextField()
    root = models.CharField(max_length=255)
    type = models.IntegerField()

    def __str__(self):
        return '{} {}'.format(self.host, self.link)


class Link(models.Model):
    link = models.URLField(max_length=500, unique=True)
    is_parsed = models.BooleanField(default=False)

    class Meta:
        db_table = 'links'
        verbose_name = _('Link')
        verbose_name_plural = _('Links')

    def __str__(self):
        return self.link


class ParsedPost(models.Model):
    title = models.CharField(max_length=500, verbose_name=_('parsed title'))
    original = RichTextField(verbose_name=_('parsed text'))
    translated_title = models.CharField(max_length=500, blank=True, null=True, verbose_name=_('translated title'))
    translated = RichTextField(verbose_name=_('translated text'), blank=True, null=True)
    rubric = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name=_('post category'),
                               blank=True, null=True)
    publisher = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('post publisher'),
                                  blank=True, null=True)
    is_processed = models.BooleanField(default=False)
    is_translated = models.BooleanField(default=False)
    is_finished = models.BooleanField(default=False)
    hash = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return self.title

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if self.is_processed and not self.is_finished:
            Post(title=self.translated_title, text=self.translated, rubric=self.rubric,
                 publisher=self.publisher, status=0).save()
            self.is_finished = True
        if not self.hash:
            self.hash = hashlib.sha256((self.title + self.original).encode('utf-8')).hexdigest()
        super().save(force_insert=False, force_update=False, using=None, update_fields=None)


class PostView(models.Model):
    fingerprint = models.CharField(max_length=255, verbose_name=_('fingerprint'))
    post_id = models.IntegerField(verbose_name=_("post identifier"))
    user_id = models.IntegerField(blank=True, null=True, verbose_name=_("user identifier"))

    def __str__(self):
        return f"{self.fingerprint} - {self.post_id}"


class UsefulStatistic(models.Model):
    fingerprint = models.CharField(max_length=255, verbose_name=_('fingerprint'))
    post_id = models.IntegerField(verbose_name=_("post identifier"))
    user_id = models.IntegerField(blank=True, null=True, verbose_name=_("user identifier"))
    is_useful = models.BooleanField(_("is useful post"))

    def __str__(self):
        return f"{self.fingerprint} - {self.post_id}"


class SearchStatistic(models.Model):
    fingerprint = models.CharField(max_length=255, verbose_name=_('fingerprint'))
    search_phrase = models.CharField(max_length=255, verbose_name=_('fingerprint'))

    def __str__(self):
        return f"{self.fingerprint} - {self.search_phrase[:40]}"
