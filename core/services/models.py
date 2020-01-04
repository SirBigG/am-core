from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from core.pro_auth.models import User

from ckeditor.fields import RichTextField


class Feedback(models.Model):
    title = models.CharField(max_length=255, verbose_name=_('Заголовок'))
    email = models.EmailField(blank=True, null=True, verbose_name=_("Email (необов'язково)"))
    text = models.TextField(verbose_name=_('Текст'))

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
    h1 = models.CharField(max_length=255, verbose_name=_('h1 tag'), blank=True, null=True)
    text = RichTextField(blank=True, null=True, verbose_name=_('meta text'))

    class Meta:
        db_table = 'metadata'
        verbose_name = _('meta data')
        verbose_name_plural = _('meta data')

    def __str__(self):
        return self.title


MARKS = [(i, i) for i in range(1, 6)]


class Reviews(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('Review owner.'))
    mark = models.IntegerField(choices=MARKS, verbose_name=_('Mark'))
    description = models.TextField(verbose_name=_('Review description'))
    date = models.DateTimeField(auto_now_add=True, verbose_name=_('Review date'))

    class Meta:
        verbose_name = _('Review')
        verbose_name_plural = _('Reviews')

    def __str__(self):
        return '%i-%s' % (self.mark, self.description)
