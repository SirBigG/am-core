from django.contrib import admin
from django.test import TestCase

from core.pro_auth.admin import UserAdmin
from core.pro_auth.models import User


class UserAdminTests(TestCase):
    def test_staff_status_and_permissions_are_available_in_admin(self):
        model_admin = UserAdmin(User, admin.site)
        field_names = {field for _title, options in model_admin.fieldsets for field in options["fields"]}

        self.assertIn("is_staff", model_admin.list_display)
        self.assertIn("is_staff", model_admin.list_filter)
        self.assertIn("groups", model_admin.list_filter)
        self.assertIn("groups", field_names)
        self.assertIn("user_permissions", field_names)
        self.assertIn("groups", model_admin.filter_horizontal)
        self.assertIn("user_permissions", model_admin.filter_horizontal)
