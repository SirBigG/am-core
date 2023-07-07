import os
from PIL import Image
from io import BytesIO
from pathlib import Path

from django.db import models
from django.core.files import File
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from core.classifier.models import Category

WIDTH = 350


class Advert(models.Model):
    title = models.CharField(max_length=512)
    description = models.TextField()
    category = models.ForeignKey(Category, blank=True, null=True, on_delete=models.SET_NULL)
    image = models.ImageField(upload_to='adverts/images', verbose_name=_('image'))
    author = models.CharField(max_length=512, blank=True, null=True)
    contact = models.CharField(max_length=512)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    location = models.ForeignKey('classifier.Location', blank=True, null=True,
                                 on_delete=models.SET_NULL, verbose_name=_('user location'))
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('advert')
        verbose_name_plural = _('adverts')
        ordering = ['created']
        indexes = [
            models.Index(fields=['created']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Cut image before save."""
        if self.image:
            im = Image.open(BytesIO(self.image.read()))
            if im.mode != 'RGB':
                im = im.convert('RGB')
            im = im.resize((WIDTH, int((float(im.size[1]) * float(WIDTH / float(im.size[0]))))), Image.LANCZOS)
            output = BytesIO()
            im.save(output, format='JPEG', quality=85)
            self.image = File(output, self.image.name)
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Delete file of image after object deleting."""
        path = self.image.path
        super().delete(using=None, keep_parents=False)
        os.remove(path)
