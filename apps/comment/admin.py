from django.contrib import admin

from .models import Comments


class CommentAdmin(admin.ModelAdmin):
    list_display = ('content_type', 'text', 'author', 'status')


admin.site.register(Comments, CommentAdmin)
