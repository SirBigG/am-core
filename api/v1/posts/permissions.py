from rest_framework.permissions import BasePermission


# TODO: create
class UserPostPermissions(BasePermission):
    """For security user post usage from other users."""
    def has_permission(self, request, view):
        return True
