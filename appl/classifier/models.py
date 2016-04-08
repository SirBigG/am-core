from __future__ import unicode_literals

from django.db import models
from django.utils.translation import ugettext_lazy as _

from mptt.models import MPTTModel, TreeForeignKey


class Country(models.Model):
    """
    Model for country.
    """
    slug = models.CharField(max_length=250, verbose_name=_('transliteration value'))
    short_slug = models.CharField(max_length=5, verbose_name=_('short slug'))
    value = models.CharField(max_length=250, unique=True, verbose_name=_('country value'))

    class Meta:
        db_table = 'country'
        verbose_name = _('country')
        verbose_name_plural = _('countries')

    def __unicode__(self):
        return self.value


class Region(models.Model):
    """
    Model for region.
    """
    slug = models.CharField(max_length=250, verbose_name=_('transliteration value'))
    value = models.CharField(max_length=250, unique=True, verbose_name=_('region value'))

    class Meta:
        db_table = 'region'
        verbose_name = _('region')
        verbose_name_plural = _('region')

    def __unicode__(self):
        return self.value


class Area(models.Model):
    """
    Model for area.
    """
    slug = models.CharField(max_length=250, verbose_name=_('transliteration value'))
    value = models.CharField(max_length=250, unique=True, verbose_name=_('area value'))

    class Meta:
        db_table = 'area'
        verbose_name = _('area')
        verbose_name_plural = _('area')

    def __unicode__(self):
        return self.value


class Location(models.Model):
    """
    Model for locations.
    """
    slug = models.CharField(max_length=250, verbose_name=_('transliteration value'))
    value = models.CharField(max_length=250, verbose_name=_('location value'))
    country = models.ForeignKey(Country, verbose_name=_('country'))
    region = models.ForeignKey(Region, verbose_name=_('region'))
    area = models.ForeignKey(Area, verbose_name=_('area'))

    class Meta:
        db_table = 'location'
        verbose_name = _('location')
        verbose_name_plural = _('locations')

    def __unicode__(self):
        return self.value


class Category(MPTTModel):
    """
    Model realize tree structure for categories.
    """
    slug = models.CharField(max_length=250, unique=True, verbose_name=_('transliteration value'))
    value = models.CharField(max_length=250, verbose_name=_('category value'))
    icon = models.CharField(max_length=250, blank=True, null=True, verbose_name=_('category icon'))
    parent = TreeForeignKey('self', blank=True, null=True, related_name='children', db_index=True,
                            verbose_name=_('category parent'))

    class MPTTMeta:
        order_insertion_by = ['slug']
        verbose_name_plural = _('Categories')

    def __unicode__(self):
        return self.value