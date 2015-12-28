from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _

import datetime


STATUS = (
    (0, _('Not active')),
    (1, _('Active')),
)


class Comments(models.Model):
    object_id = models.IntegerField(verbose_name=_('object id'))
    content_type = models.ForeignKey(ContentType, verbose_name=_('content type of object'))
    text = models.TextField(verbose_name=_('comment text'))
    author = models.ForeignKey(User, verbose_name=_('comment author'))
    publish_date = models.DateTimeField(default=datetime.datetime.now)
    status = models.IntegerField(choices=STATUS, default=1, verbose_name=_('comment status'))

    class Meta:
        db_table = 'comments'
        verbose_name = _('comment')
        verbose_name_plural = _('comments')

    def __unicode__(self):
        return self.text
