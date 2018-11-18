from PIL import Image
from io import BytesIO

from django.db import models
from django.core.cache import cache
from django.utils.translation import get_language
from django.urls import reverse
from django.core.files import File

from core.pro_auth.models import User

from transliterate import slugify

from ckeditor.fields import RichTextField


class EventType(models.Model):
    title = models.CharField(max_length=255)
    slug = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title.lower(), get_language()[:2])
        super().save(*args, **kwargs)


class Event(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=255)
    slug = models.CharField(max_length=250, unique=True)
    address = models.CharField(max_length=350)
    text = RichTextField()
    status = models.BooleanField(default=0)
    start = models.DateTimeField()
    stop = models.DateTimeField()
    type = models.ForeignKey(EventType, on_delete=models.CASCADE, related_name='event_types')
    location = models.ForeignKey('classifier.Location', on_delete=models.CASCADE)
    poster = models.ImageField(upload_to="posters")

    def __str__(self):
        return self.title

    MAIN_CACHE_KEY = 'event_main_cache_key'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify('{} {}'.format(self.title.lower(), self.location.slug), get_language()[:2])
        if self.poster:
            im = Image.open(BytesIO(self.poster.read()))
            if im.mode != 'RGB':
                im = im.convert('RGB')
            im.thumbnail((1000, 800), Image.ANTIALIAS)
            output = BytesIO()
            im.save(output, format='JPEG', quality=85)
            self.poster = File(output, self.poster.name)
        super().save(*args, **kwargs)
        cache.delete(self.MAIN_CACHE_KEY)

    def get_absolute_url(self):
        return reverse('events:event-detail', args=(self.slug, ))
