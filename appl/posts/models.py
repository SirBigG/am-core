# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone

from appl.pro_auth.models import User

from appl.classifier.models import Category

from ckeditor.fields import RichTextField

WORK_STATUS = (
    (1, _('Translate')),
    (2, _('Publish')),
)


class Post(models.Model):
    """
    Posts model.
    """
    title = models.CharField(max_length=500, verbose_name=_('post title'))
    text = RichTextField(verbose_name=_('post text'))
    slug = models.CharField(max_length=250, unique=True, verbose_name=_('transliteration value'))
    work_status = models.IntegerField(choices=WORK_STATUS, default=None,
                                      blank=True, null=True,
                                      verbose_name=_('status of author work'))
    author = models.CharField(max_length=250, blank=True, null=True, verbose_name=_('post author'))
    source = models.CharField(max_length=250, blank=True, null=True, verbose_name=_('post source'))

    publisher = models.ForeignKey(User, verbose_name=_('post publisher'))
    publish_date = models.DateTimeField(_('date of publish'), default=timezone.now)

    hits = models.IntegerField(default=0, verbose_name=_('count of views'))

    status = models.BooleanField(default=1, verbose_name=_('post status'))

    rubric = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name=_('post category'))

    class Meta:
        db_table = 'post'
        verbose_name = _('Post')
        verbose_name_plural = _('Posts')

    def __unicode__(self):
        return self.title

    def get_absolute_url(self):
        anc = self.rubric.get_family()[1:]
        s = ''
        for a in anc:
            s += '/' + a.slug
        url = s + '/' + self.slug + '-' + str(self.pk) + '.html'
        return url


class Photo(models.Model):
    """
    Post photos model.
    """
    image = models.ImageField(upload_to='uploads', verbose_name=_('image'))
    description = models.CharField(max_length=500, blank=True, null=True, verbose_name=_('photo describing'))
    post = models.ForeignKey(Post, on_delete=models.CASCADE, verbose_name=_('post of photo'), related_name='photo')
    author = models.CharField(max_length=150, blank=True, null=True, verbose_name=_('author of photo'))
    source = models.CharField(max_length=150, blank=True, null=True, verbose_name=_('photo source'))

    class Meta:
        db_table = 'photo'
        verbose_name = _('Photo')
        verbose_name_plural = _('Photos')

    def __unicode__(self):
        return unicode(self.id)

    def save(self, *args, **kwargs):
        if self.image:
            from PIL import Image
            import StringIO
            from django.core.files import File
            im = Image.open(StringIO.StringIO(self.image.read()))
            im.thumbnail((1000, 800), Image.ANTIALIAS)
            output = StringIO.StringIO()
            im.save(output, format='JPEG', quality=85)
            self.image = File(output, self.image.name)
        super(Photo, self).save(*args, **kwargs)


class Comment(models.Model):
    """
    Post comments model.
    """
    post = models.ForeignKey(Post, on_delete=models.CASCADE, verbose_name=_('post of comment'))
    text = models.TextField(verbose_name=_('comment text'))
    date = models.DateTimeField(_('comment date'), default=timezone.now)
    user = models.ForeignKey(User, verbose_name=_('comment owner'))

    class Meta:
        db_table = 'comment'
        verbose_name = _('Comment')
        verbose_name_plural = _('Comments')

    def __unicode__(self):
        return unicode(self.user)
