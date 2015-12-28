from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from apps.classifier.models import Category

import datetime


class PostPhoto(models.Model):
    class Meta:
        db_table = 'post_photo'
        verbose_name = _('post photo')
        verbose_name_plural = _('post photos')

    post_photo_field = models.ImageField(
        upload_to='uploads/post_photos/', verbose_name=_('post photo')
    )


class Post(models.Model):
    title = models.CharField(max_length=150, verbose_name=_('title'))
    post_category = models.ForeignKey(Category, verbose_name=_('category'))
    date = models.DateTimeField(verbose_name=_('date'), default=datetime.datetime.now)
    text = models.TextField(verbose_name=_('text'))
    post_images = models.ManyToManyField(PostPhoto, verbose_name=_('post images'))
    publisher = models.ForeignKey(User, verbose_name=_('post publisher'))
    author = models.CharField(max_length=100, verbose_name=_('post author'), blank=True)

    class Meta:
        db_table = 'post'
        verbose_name = _('post')
        verbose_name_plural = _('posts')

    def get_absolute_url(self):
        return '/posts/%s/%i/' % (self.post_category.slug, self.id)

    def __unicode__(self):
        return self.title
