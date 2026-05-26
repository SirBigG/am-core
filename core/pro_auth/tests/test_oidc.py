from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from oauth2_provider.models import get_application_model

from core.pro_auth.oauth_validators import ForumOIDCValidator
from core.pro_auth.pipeline import create_user
from core.utils.tests.factories import UserFactory


class EnsureForumOIDCApplicationCommandTests(TestCase):
    def test_creates_forum_oidc_application(self):
        owner = UserFactory(is_staff=True)
        out = StringIO()

        call_command(
            "ensure_forum_oidc_application",
            client_id="forum-client",
            client_secret="secret",
            redirect_uri="https://forum.example.com/complete/oidc/",
            post_logout_redirect_uri="https://example.com/",
            owner_email=owner.email,
            stdout=out,
        )

        Application = get_application_model()
        application = Application.objects.get(client_id="forum-client")
        self.assertEqual(application.name, "AgroMega Forum")
        self.assertEqual(application.user, owner)
        self.assertEqual(application.redirect_uris, "https://forum.example.com/complete/oidc/")
        self.assertTrue(application.skip_authorization)
        self.assertIn("Created OIDC application", out.getvalue())

    def test_requires_client_secret(self):
        with self.assertRaises(CommandError):
            call_command("ensure_forum_oidc_application", client_secret="")


class FakeStrategy:
    def __init__(self):
        self.created_user_data = None

    def create_user(self, **fields):
        self.created_user_data = fields
        return UserFactory(**fields)


class FakeBackend:
    name = "oidc"

    def __init__(self, user_pk=None):
        self.strategy = self
        self.user_pk = user_pk

    def session_pop(self, key):
        self.assert_key = key
        value = self.user_pk
        self.user_pk = None
        return value

    def setting(self, name, default):
        return default


class MainSocialAuthPipelineTests(TestCase):
    def test_create_user_reuses_user_from_session(self):
        user = UserFactory()
        backend = FakeBackend(user_pk=user.pk)

        result = create_user(FakeStrategy(), {}, backend)

        self.assertEqual(result, {"is_new": False, "user": user})

    def test_create_user_stores_social_details(self):
        strategy = FakeStrategy()
        backend = FakeBackend()
        details = {"email": "social@example.com", "first_name": "Social"}

        result = create_user(strategy, details, backend)

        self.assertTrue(result["is_new"])
        self.assertEqual(result["user"].email, "social@example.com")
        self.assertEqual(strategy.created_user_data["details"], details)


class ForumOIDCValidatorTests(TestCase):
    def test_additional_claims_include_forum_profile_fields(self):
        user = UserFactory(first_name="Jane", last_name="Doe", is_staff=True, is_superuser=True)
        request = type("Request", (), {"user": user})()

        claims = ForumOIDCValidator().get_additional_claims()

        self.assertEqual(claims["email"](request), user.email)
        self.assertEqual(claims["given_name"](request), "Jane")
        self.assertEqual(claims["family_name"](request), "Doe")
        self.assertEqual(claims["name"](request), "Jane Doe")
        self.assertTrue(claims["is_staff"](request))
        self.assertTrue(claims["is_superuser"](request))


class SocialOIDCBeginViewTests(TestCase):
    @override_settings(SITE_URL="https://example.com", FORUM_BASE_URL="https://forum.example.com")
    def test_redirects_to_oauth_authorize_url(self):
        with patch.dict("os.environ", {"FORUM_OIDC_REDIRECT_URI": "https://forum.example.com/complete/oidc/"}):
            response = self.client.get("/social/login/oidc/", {"next": "https://forum.example.com/topic/1/"})

        self.assertEqual(response.status_code, 302)
        location = response["Location"]
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        self.assertEqual(f"{parsed.scheme}://{parsed.netloc}{parsed.path}", "https://example.com/o/authorize/")
        self.assertEqual(params["client_id"], ["agromega-forum"])
        self.assertEqual(params["redirect_uri"], ["https://forum.example.com/complete/oidc/"])
        self.assertEqual(params["response_type"], ["code"])
        self.assertEqual(params["scope"], ["openid profile email"])
        self.assertEqual(params["state"], ["https://forum.example.com/topic/1/"])
