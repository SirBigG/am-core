from urllib.parse import urljoin

from django.conf import settings
from oauth2_provider.oauth2_validators import OAuth2Validator


class ForumOIDCValidator(OAuth2Validator):
    def get_additional_claims(self):
        return {
            "email": lambda request: request.user.email or "",
            "email_verified": lambda request: False,
            "given_name": lambda request: request.user.first_name or "",
            "family_name": lambda request: request.user.last_name or "",
            "name": lambda request: request.user.get_full_name(),
            "preferred_username": lambda request: request.user.get_full_name(),
            "picture": lambda request: self._avatar_url(request),
            "is_staff": lambda request: request.user.is_staff,
            "is_superuser": lambda request: request.user.is_superuser,
        }

    def get_discovery_claims(self, request):
        return [
            "sub",
            "email",
            "email_verified",
            "given_name",
            "family_name",
            "name",
            "preferred_username",
            "picture",
            "is_staff",
            "is_superuser",
        ]

    @staticmethod
    def _avatar_url(request):
        user = request.user
        if not getattr(user, "avatar", None):
            return ""
        try:
            return urljoin(f"{settings.SITE_URL}/", user.avatar.url.lstrip("/"))
        except ValueError:
            return ""
