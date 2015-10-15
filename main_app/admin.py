from django.contrib import admin
from django import forms
from models import Post, Region, Category, PostPhoto, UserInformation

# Register your models here.
class PostAdmin(admin.ModelAdmin):
    fields = ['title', 'post_category', 'date', 'post_images', 'text']
    list_display = ('title', 'post_category', 'date')

class UserInformationAdmin(admin.ModelAdmin):
    list_display = ('profile','location','phone')

admin.site.register(UserInformation,UserInformationAdmin)
admin.site.register(Region)
admin.site.register(Category)
admin.site.register(PostPhoto)
admin.site.register(Post, PostAdmin)