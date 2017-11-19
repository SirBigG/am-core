from django.db import models
from django.core.cache import cache
from django.utils.translation import get_language
from django.core.urlresolvers import reverse

from transliterate import slugify


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
    title = models.CharField(max_length=255)
    slug = models.CharField(max_length=250, unique=True)
    text = models.TextField()
    status = models.BooleanField(default=0)
    start = models.DateTimeField()
    stop = models.DateTimeField()
    type = models.ForeignKey(EventType)
    location = models.ForeignKey('classifier.Location')
    poster = models.ImageField(upload_to="posters", blank=True, null=True)

    def __str__(self):
        return self.title

    MAIN_CACHE_KEY = 'event_main_cache_key'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify('{} {}'.format(self.title.lower(), self.location.slug), get_language()[:2])
        super().save(*args, **kwargs)
        cache.delete(self.MAIN_CACHE_KEY)

    def get_absolute_url(self):
        return reverse('events:event-detail', args=(self.slug, ))
