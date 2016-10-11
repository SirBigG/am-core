from modeltranslation.translator import register, TranslationOptions

from core.posts.models import Post, Photo


@register(Post)
class PostTranslation(TranslationOptions):
    fields = ('title', 'text', 'author', 'source',)


@register(Photo)
class PhotoTranslation(TranslationOptions):
    fields = ('description', 'author', 'source',)
