from PIL import Image
from io import BytesIO
from pathlib import Path

from django.db import models
from django.utils.translation import get_language, ugettext_lazy as _
from django.utils import timezone
from django.urls import reverse
from django.core.files import File
from django.conf import settings

from core.pro_auth.models import User

from core.classifier.models import Category
from core.services.models import MetaData

from ckeditor.fields import RichTextField

from transliterate import slugify

WORK_STATUS = (
    (1, _('Translate')),
    (2, _('Publish')),
)


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

    class Meta:
        db_table = 'post'
        verbose_name = _('Post')
        verbose_name_plural = _('Posts')
        ordering = ['-publish_date']

    def __str__(self):
        return self.title

    def _save_category(self):
        if self.rubric.is_for_user:
            try:
                category = Category.objects.get(slug=self.slug, parent=self.rubric)
                if category.value != self.title:
                    category.value = self.title
                    category.save()
            except Category.DoesNotExist:
                Category.objects.create(slug=self.slug, parent=self.rubric, value=self.title)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title.lower(), get_language()[:2])
        self._save_category()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('post-detail', args=(self.rubric.parent.slug, self.rubric.slug,
                                            self.slug, self.pk,))


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
        return '%s/%s' % (str(path), path_dict[-1])

    def thumbnail(self, width=300, height=200):
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
                im.thumbnail((width, height), Image.ANTIALIAS)
                im.save(thumb_path, format='JPEG')
            return ('%s%s' % (settings.MEDIA_URL, str(thumb_path).replace(settings.MEDIA_ROOT, ""))).replace('//', '/')

    def save(self, *args, **kwargs):
        """Cut image before save."""
        if self.image:
            im = Image.open(BytesIO(self.image.read()))
            im.thumbnail((1000, 800), Image.ANTIALIAS)
            output = BytesIO()
            im.save(output, format='JPEG', quality=85)
            self.image = File(output, self.image.name)
        super(Photo, self).save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Delete file of image after object deleting."""
        path = self.image.path
        super(Photo, self).delete(using=None, keep_parents=False)
        import os
        os.remove(path)


class Comment(models.Model):
    """Post comments model."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, verbose_name=_('post of comment'))
    text = models.TextField(verbose_name=_('comment text'))
    date = models.DateTimeField(_('comment date'), default=timezone.now)
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('comment owner'))

    class Meta:
        db_table = 'comment'
        verbose_name = _('Comment')
        verbose_name_plural = _('Comments')

    def __str__(self):
        return str(self.user)
