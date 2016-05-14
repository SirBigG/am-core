from django.contrib import admin

from appl.services.models import Feedback


class FeedbackAdmin(admin.ModelAdmin):
    model = Feedback
    list_display = ('title', 'email')

admin.site.register(Feedback, FeedbackAdmin)
