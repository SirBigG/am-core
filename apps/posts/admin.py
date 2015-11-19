from django.contrib import admin

from .models import Category, Post, PostPhoto


class PostAdmin(admin.ModelAdmin):
    fields = ('title', 'post_category', 'text',
              'post_images', ('author', 'publisher'), 'date')

    list_display = ('title', 'post_category',
                    'publisher', 'date')


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'level', 'parent')


admin.site.register(Post, PostAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(PostPhoto)
