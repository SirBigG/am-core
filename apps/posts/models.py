from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

import datetime


class Category(models.Model):
    class Meta:
        db_table = 'category'
        verbose_name = _('category')
        verbose_name_plural = _('categories')

    category_field = models.CharField(
        max_length=20, verbose_name=_('category')
    )
    translit = models.CharField(max_length=20, verbose_name=_('category translit'))

    def __unicode__(self):
        return self.category_field


class PostPhoto(models.Model):
    class Meta:
        db_table = 'post_photo'
        verbose_name = _('post photo')
        verbose_name_plural = _('post photos')

    post_photo_field = models.ImageField(
        upload_to='uploads/post_photos/', verbose_name=_('post photo')
    )


class Post(models.Model):
    class Meta:
        db_table = 'post'
        verbose_name = _('post')
        verbose_name_plural = _('posts')

    post_category = models.ForeignKey(Category, verbose_name=_('category'))
    title = models.CharField(max_length=150, verbose_name=_('title'))
    date = models.DateTimeField(verbose_name=_('date'), default=datetime.datetime.now)
    text = models.TextField(verbose_name=_('text'))
    post_images = models.ManyToManyField(PostPhoto, verbose_name=_('post images'))
    publisher = models.ForeignKey(User, verbose_name=_('post publisher'))
    author = models.CharField(max_length=100, verbose_name=_('post author'), blank=True)

    def __unicode__(self):
        return self.title

class Comments(models.Model):
    class Meta:
        db_table = 'post_comments'
        verbose_name = _('comment')
        verbose_name_plural = _('comments')

    post = models.ForeignKey(Post)
    text = models.TextField(verbose_name=_('comment text'))
    author = models.ForeignKey(User, verbose_name=_('comment author'))
    publish_date = models.DateTimeField(default=datetime.datetime.now)

    def __unicode__(self):
        return self.text
