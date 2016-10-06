from __future__ import unicode_literals

from django.db import models
from django.utils.translation import ugettext_lazy as _


class Feedback(models.Model):
    title = models.CharField(max_length=255, verbose_name=_('feedback topic'))
    email = models.EmailField(verbose_name=_('feedback email'))
    text = models.TextField(verbose_name=_('feedback body'))

    class Meta:
        db_table = 'feedback'
        verbose_name = _('Feedback')
        verbose_name_plural = _('Feedbacks')

    def __str__(self):
        return self.title


class MetaData(models.Model):
    """Stores meta data for seo optimizing."""
    title = models.CharField(max_length=255, verbose_name=_('meta title'))
    description = models.CharField(max_length=255, verbose_name=_('meta description'))
    h1 = models.CharField(max_length=255, verbose_name=_('meta_description'), blank=True, null=True)

    class Meta:
        db_table = 'metadata'
        verbose_name = _('meta data')
        verbose_name_plural = _('meta data')

    def __str__(self):
        return self.title
