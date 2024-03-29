from django.contrib import admin

from core.pro_auth.models import User
from core.pro_auth.forms import AdminUserCreationForm, AdminUserChangeForm

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _


class UserAdmin(BaseUserAdmin):
    """
    Representation custom user in admin site.
    """
    form = AdminUserChangeForm
    add_form = AdminUserCreationForm

    list_display = ('email', 'phone1', 'birth_date', 'date_joined',
                    'is_superuser', 'number_of_characters')
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

    def number_of_characters(self, obj):
        from core.posts.models import Post
        return len(''.join(Post.objects.filter(publisher_id=obj.pk,
                                               status=False).values_list('text', flat=True)).replace(' ', ''))


admin.site.register(User, UserAdmin)
