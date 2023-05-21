from django.contrib import admin
from django.contrib.flatpages.admin import FlatPageAdmin
from django.contrib.flatpages.models import FlatPage
from django.utils.translation import gettext_lazy as _

from core.services.models import Feedback, MetaData, Reviews


class FeedbackAdmin(admin.ModelAdmin):
    model = Feedback
    list_display = ('title', 'email', 'text', 'created')


class FlatPageAdmin(FlatPageAdmin):
    fieldsets = (
        (None, {'fields': ('url', 'title', 'content', 'sites')}),
        (_('Advanced options'), {
            'classes': ('collapse', ),
            'fields': (
                'enable_comments',
                'registration_required',
                'template_name',
            ),
        }),
    )


admin.site.unregister(FlatPage)
admin.site.register(FlatPage, FlatPageAdmin)
admin.site.register(Feedback, FeedbackAdmin)
admin.site.register(MetaData)
admin.site.register(Reviews)
