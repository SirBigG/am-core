from django.contrib import admin

from appl.posts.models import Post, Photo, Comment

from modeltranslation.admin import TranslationAdmin, TranslationTabularInline


class PhotoInLine(TranslationTabularInline):
    model = Photo


class PostAdmin(TranslationAdmin):
    inlines = [
        PhotoInLine,
    ]
    list_display = ('title', 'publisher', 'publish_date', 'hits', 'status', )

    def get_form(self, request, obj=None, **kwargs):
        form = super(PostAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['publisher'].initial = request.user
        return form

admin.site.register(Post, PostAdmin)
admin.site.register(Comment)
