# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _


class AnnouncementPhoto(models.Model):
    class Meta:
        db_table = 'announcement_photo'
        verbose_name = _('announcement photo')
        verbose_name_plural = _('announcement photos')

    announcement_photo = models.ImageField(
        upload_to='uploads/announcement_photos/', verbose_name=_('announcement photo')
    )


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