from django.contrib import admin

from appl.services.models import Feedback, MetaData

from modeltranslation.admin import TranslationAdmin


class FeedbackAdmin(admin.ModelAdmin):
    model = Feedback
    list_display = ('title', 'email')

admin.site.register(Feedback, FeedbackAdmin)
admin.site.register(MetaData, TranslationAdmin)
