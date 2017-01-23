from rest_framework.permissions import BasePermission, IsAuthenticated


SECURE_METHODS = ['POST', 'PUT', 'DELETE', 'PATCH']


class CreateUpdatePermission(BasePermission):
    """For security user information from other users."""
    def has_permission(self, request, view):
        if request.method in SECURE_METHODS:
            return IsAuthenticated().has_permission(request, view)
        return True
