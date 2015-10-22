from django.contrib import admin

from .models import UserInformation

# Register your models here.
class UserInformationAdmin(admin.ModelAdmin):
    list_display = ('profile','location','phone')

admin.site.register(UserInformation,UserInformationAdmin)