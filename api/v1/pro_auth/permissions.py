from rest_framework.permissions import BasePermission


class PersonalPermission(BasePermission):
    """For security user information from other users."""
    def has_permission(self, request, view):
        return request.user == view.get_object()
