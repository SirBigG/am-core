from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings


class News(models.Model):
    title = models.CharField(max_length=500)
    link = models.URLField()
    poster = models.URLField(null=True, blank=True)
    extra = models.TextField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'news'
        verbose_name = _('News')
        verbose_name_plural = _('News')

    def get_absolute_url(self):
        return "%s/news/list/#%i" % (settings.HOST, self.pk)
