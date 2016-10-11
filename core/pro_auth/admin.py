from django.contrib import admin

from core.pro_auth.models import User
from core.pro_auth.forms import UserCreationForm, AdminUserChangeForm

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import ugettext_lazy as _


class UserAdmin(BaseUserAdmin):
    """
    Representation custom user in admin site.
    """
    form = AdminUserChangeForm
    add_form = UserCreationForm

    list_display = ('email', 'phone1', 'birth_date', 'date_joined',
                    'is_superuser')
    list_filter = ('is_superuser',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Phones'), {'fields': ('phone1', 'phone2', 'phone3')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'location', 'birth_date',
                                         'date_joined')}),
        (_('Permissions'), {'fields': ('is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'phone1', 'location', 'password1', 'password2')}
         ),
    )
    search_fields = ('email',)
    ordering = ('email',)
    filter_horizontal = ()


admin.site.register(User, UserAdmin)
