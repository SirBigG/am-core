from django.db import models
from django.utils.translation import ugettext_lazy as _


class Category(models.Model):
    title = models.CharField(
        max_length=50, verbose_name=_('category')
    )
    slug = models.SlugField(max_length=20, verbose_name=_('category slug'), unique=True)
    level = models.IntegerField(verbose_name=_('level'))
    parent = models.CharField(max_length=20, default='root', verbose_name=_('category parent'))
    description = models.TextField(verbose_name=_('description'), blank=True)

    class Meta:
        db_table = 'category'
        verbose_name = _('category')
        verbose_name_plural = _('categories')

    def get_absolute_url(self):
        return '/posts/%s/' % self.slug

    def __unicode__(self):
        return self.title
