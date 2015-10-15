#-*- coding: utf-8 -*-

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _


class Region(models.Model):
    class Meta:
        db_table = "region"
        verbose_name = _('region')
        verbose_name_plural = _('regions')

    region_field = models.CharField(max_length=20, verbose_name=_('region'))

    def __unicode__(self):
        return self.region_field


class Category(models.Model):
    class Meta:
        db_table = 'category'
        verbose_name = _('category')
        verbose_name_plural = _('categories')

    category_field = models.CharField(
        max_length=20, verbose_name=_('category')
    )

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


class AnnouncementPhoto(models.Model):
    class Meta:
        db_table = 'announcement_photo'
        verbose_name = _('announcement photo')
        verbose_name_plural = _('announcement photos')

    announcement_photo = models.ImageField(
        upload_to='uploads/announcement_photos/', verbose_name=_('announcement photo')
    )


class UserInformation(models.Model):
    class Meta:
        db_table = "user_information"
        verbose_name = _('user information')
        verbose_name_plural = _('user information')

    profile = models.ForeignKey(User, unique=True)
    avatar = models.ImageField(
        upload_to='uploads/avatars/', verbose_name=_('avatar'),
        blank=True
    )
    location = models.ForeignKey(Region, verbose_name=_('location'),default=2)
    phone = models.IntegerField(unique=True,verbose_name=_('phone'), blank=True)
    birth_date = models.DateField(verbose_name=_('birth date'), blank=True)
    about = models.TextField(verbose_name=_('about you'), blank=True)
    breed = models.TextField(verbose_name=_('pigeons breed'), blank=True)

    def __unicode__(self):
        return self.about


class Post(models.Model):
    class Meta:
        db_table = 'post'
        verbose_name = _('post')
        verbose_name_plural = _('posts')

    post_category = models.ForeignKey(Category, verbose_name=_('category'), default=2)
    title = models.CharField(max_length=150, verbose_name=_('title'))
    date = models.DateTimeField(verbose_name=_('date'))
    text = models.TextField(verbose_name=_('text'))
    post_images = models.ManyToManyField(PostPhoto, verbose_name=_('post images'))

    def __unicode__(self):
        return self.title


class Announcement(models.Model):
    class Meta:
        db_table = 'announcement'
        verbose_name = _('announcement')
        verbose_name_plural = _('announcements')

    author = models.ForeignKey(User)
    title = models.CharField(max_length=150, verbose_name=_('announcement title'))
    date = models.DateTimeField(verbose_name=_('date'))
    ann_photo = models.ManyToManyField(AnnouncementPhoto, verbose_name=_('announcements photo'))
    text = models.TextField(verbose_name=_('announcement text'))

    def __unicode__(self):
        return self.title