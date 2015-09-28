from django.contrib import admin
from models import Post, Region, Category, PostPhoto

# Register your models here.

admin.site.register(Region)
admin.site.register(Category)
admin.site.register(PostPhoto)
admin.site.register(Post)