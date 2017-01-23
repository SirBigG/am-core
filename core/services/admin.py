from django.contrib import admin

from core.services.models import Feedback, MetaData, Comments, Reviews

from modeltranslation.admin import TranslationAdmin

from mptt.admin import DraggableMPTTAdmin


class FeedbackAdmin(admin.ModelAdmin):
    model = Feedback
    list_display = ('title', 'email')

admin.site.register(Feedback, FeedbackAdmin)
admin.site.register(MetaData, TranslationAdmin)
admin.site.register(Comments, DraggableMPTTAdmin)
admin.site.register(Reviews)
