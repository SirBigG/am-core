import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Creates or updates the OpenID Connect client used by the forum instance."

    def add_arguments(self, parser):
        parser.add_argument("--client-id", default=os.getenv("FORUM_OIDC_CLIENT_ID", "agromega-forum"))
        parser.add_argument("--client-secret", default=os.getenv("FORUM_OIDC_CLIENT_SECRET"))
        parser.add_argument(
            "--redirect-uri",
            default=os.getenv("FORUM_OIDC_REDIRECT_URI", f"{settings.FORUM_BASE_URL}/complete/oidc/"),
        )
        parser.add_argument(
            "--post-logout-redirect-uri",
            default=os.getenv("FORUM_OIDC_POST_LOGOUT_REDIRECT_URI", settings.SITE_URL),
        )
        parser.add_argument("--owner-email", default=os.getenv("FORUM_OIDC_OWNER_EMAIL"))

    def handle(self, *args, **options):
        if not options["client_secret"]:
            raise CommandError("Provide --client-secret or FORUM_OIDC_CLIENT_SECRET.")

        from oauth2_provider.models import get_application_model

        Application = get_application_model()
        owner = self._get_owner(options["owner_email"])
        field_names = {field.name for field in Application._meta.get_fields()}
        defaults = {
            "name": "AgroMega Forum",
            "user": owner,
            "client_secret": options["client_secret"],
            "client_type": getattr(Application, "CLIENT_CONFIDENTIAL", "confidential"),
            "authorization_grant_type": getattr(Application, "GRANT_AUTHORIZATION_CODE", "authorization-code"),
            "redirect_uris": options["redirect_uri"],
            "skip_authorization": True,
        }

        if "algorithm" in field_names:
            defaults["algorithm"] = getattr(
                Application,
                "RS256_ALGORITHM",
                getattr(Application, "ALGORITHM_RS256", "RS256"),
            )
        if "post_logout_redirect_uris" in field_names:
            defaults["post_logout_redirect_uris"] = options["post_logout_redirect_uri"]

        application, created = Application.objects.update_or_create(
            client_id=options["client_id"],
            defaults=defaults,
        )
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} OIDC application {application.client_id!r}."))

    @staticmethod
    def _get_owner(owner_email):
        User = get_user_model()
        if owner_email:
            return User.objects.get(email=owner_email)
        return (
            User.objects.filter(is_superuser=True).order_by("pk").first() or User.objects.filter(is_staff=True).first()
        )
