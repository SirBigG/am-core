from rest_framework.permissions import BasePermission


class IsParserWorker(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.auth
            and request.user
            and request.user.is_authenticated
            and request.user.has_perm("companies.use_parser_worker_api")
        )
