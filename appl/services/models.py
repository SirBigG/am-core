from __future__ import unicode_literals

from django.db import models
from django.utils.translation import ugettext_lazy as _


class Feedback(models.Model):
    title = models.CharField(max_length=255, verbose_name=_('feedback topic'))
    email = models.EmailField(verbose_name=_('feedback email'))
    text = models.TextField(verbose_name=_('feedback body'))

    class Meta:
        db_table = 'feedback'
        verbose_name = 'Feedback'
        verbose_name_plural = 'Feedbacks'

    def __unicode__(self):
        return self.title
