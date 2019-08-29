from datetime import date

from django import template
from django.core.cache import cache

from core.events.models import Event

register = template.Library()


EVENTS_COUNT = 5


@register.inclusion_tag('events/main_list.html')
def events_list():
    events = cache.get(Event.MAIN_CACHE_KEY)
    if events is None:
        events = list(Event.objects.select_related('location').filter(
            status=1, start__gte=date.today()).order_by('start'))
        cache.set(Event.MAIN_CACHE_KEY, events)
    return {'events': events}


@register.inclusion_tag('events/index_carousel.html')
def index_carousel():
    events = cache.get(Event.INDEX_CACHE_KEY)
    if events is None:
        events = list(Event.objects.select_related('location').filter(
            status=1, start__gte=date.today()).order_by('start')[:3])
        cache.set(Event.INDEX_CACHE_KEY, events, 60 * 5)
    return {'object_list': events}
