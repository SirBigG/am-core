from io import BytesIO

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.files import File

from mptt.models import MPTTModel, TreeForeignKey

from PIL import Image

from core.services.models import MetaData


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
        ordering = ["value"]

    def __str__(self):
        return self.value


class Region(models.Model):
    """
    Model for region.
    """
    slug = models.CharField(max_length=250, verbose_name=_('transliteration value'))
    value = models.CharField(max_length=250, unique=True, verbose_name=_('region value'))
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='region_country',
                                verbose_name=_('region country'))

    class Meta:
        db_table = 'region'
        verbose_name = _('region')
        verbose_name_plural = _('region')

    def __str__(self):
        return self.value


class Area(models.Model):
    """
    Model for area.
    """
    slug = models.CharField(max_length=250, verbose_name=_('transliteration value'))
    value = models.CharField(max_length=250, verbose_name=_('area value'))
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='area_region',
                               verbose_name=_('area region'))

    class Meta:
        db_table = 'area'
        verbose_name = _('area')
        verbose_name_plural = _('area')

    def __str__(self):
        return self.value


class Location(models.Model):
    """
    Model for locations.
    """
    slug = models.CharField(max_length=250, verbose_name=_('transliteration value'))
    value = models.CharField(max_length=250, verbose_name=_('location value'))
    country = models.ForeignKey(Country, on_delete=models.CASCADE, verbose_name=_('country'))
    region = models.ForeignKey(Region, on_delete=models.CASCADE, verbose_name=_('region'))
    area = models.ForeignKey(Area, on_delete=models.CASCADE, verbose_name=_('area'))
    longitude = models.FloatField(verbose_name=_('location longitude'), blank=True, null=True)
    latitude = models.FloatField(verbose_name=_('location latitude'), blank=True, null=True)

    class Meta:
        db_table = 'location'
        verbose_name = _('location')
        verbose_name_plural = _('locations')

    def __str__(self):
        return '%s (%s %s)' % (self.value, str(self.region), str(self.area))


class Category(MPTTModel):
    """
    Model realize tree structure for categories.
    """
    slug = models.CharField(max_length=250, unique=True, verbose_name=_('transliteration value'))
    value = models.CharField(max_length=250, verbose_name=_('category value'))
    icon = models.CharField(max_length=250, blank=True, null=True, verbose_name=_('category icon'))
    parent = TreeForeignKey('self', blank=True, null=True, related_name='children', db_index=True,
                            on_delete=models.CASCADE, verbose_name=_('category parent'))
    is_for_user = models.BooleanField(default=False, verbose_name=_('user relation for post category'))
    is_active = models.BooleanField(default=True, verbose_name=_('for feel on off'))

    image = models.ImageField(upload_to='categories', blank=True, null=True)

    meta = models.OneToOneField(MetaData, on_delete=models.CASCADE, blank=True, null=True,
                                verbose_name=_('category meta data'), related_name='category-meta-data+')

    class MPTTMeta:
        order_insertion_by = ['slug']
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')

    def __str__(self):
        return self.value

    def get_absolute_url(self):
        return '/%s/' % '/'.join(self.get_ancestors(include_self=True).values_list('slug', flat=True)[1:])

    def save(self, *args, **kwargs):
        if self.image:
            HEIGHT = 200
            WIDTH = 300
            img = Image.open(BytesIO(self.image.read()))
            hsize = int(float(img.size[1]) * float(WIDTH) / float(img.size[0]))
            if hsize >= HEIGHT:
                img = img.resize((WIDTH, hsize), Image.LANCZOS)
                delta = hsize - HEIGHT if hsize > HEIGHT else 0
                img = img.crop((0, delta / 2, WIDTH, hsize - (delta / 2)))
            elif hsize < HEIGHT:
                wsize = int(float(img.size[0]) * float(HEIGHT) / float(img.size[1]))
                img = img.resize((wsize, HEIGHT), Image.LANCZOS)
                delta = wsize - WIDTH if wsize > WIDTH else 0
                img = img.crop((delta / 2, 0, wsize - (delta / 2), HEIGHT))
            else:
                # If not height resize with auto height
                img = img.resize((WIDTH, hsize), Image.LANCZOS)
            output = BytesIO()
            img.save(output, 'JPEG')
            self.image = File(output, name=self.image.name)
        super().save(*args, **kwargs)
