from rest_framework.permissions import BasePermission


class IsParserWorker(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.auth
            and request.user
            and request.user.is_authenticated
            and request.user.has_perm("companies.use_parser_worker_api")
        )


class CanManageParserCatalog(IsParserWorker):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        action = {"POST": "add", "PUT": "change", "PATCH": "change"}.get(request.method)
        return not action or request.user.has_perm(f"companies.{action}_{view.catalog_model}")
