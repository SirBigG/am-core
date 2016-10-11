from modeltranslation.translator import register, TranslationOptions

from core.classifier.models import Country, Region, Area, Location, Category


@register(Country)
class CountryTranslation(TranslationOptions):
    fields = ('value', )


@register(Region)
class RegionTranslation(TranslationOptions):
    fields = ('value',)


@register(Area)
class AreaTranslation(TranslationOptions):
    fields = ('value',)


@register(Location)
class LocationTranslation(TranslationOptions):
    fields = ('value',)


@register(Category)
class CategoryTranslation(TranslationOptions):
    fields = ('value',)
