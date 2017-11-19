from modeltranslation.translator import register, TranslationOptions

from .models import EventType


@register(EventType)
class EventTypeTranslation(TranslationOptions):
    fields = ('title', )
