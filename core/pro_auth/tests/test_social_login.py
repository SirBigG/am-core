from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from social_django.models import UserSocialAuth

from core.pro_auth.models import User


class FormParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = {"attrs": attrs, "inputs": {}}
            self.forms.append(self.current)
        elif tag == "input" and self.current is not None:
            self.current["inputs"][attrs.get("name")] = attrs.get("value")

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


@override_settings(
    SOCIAL_AUTH_GOOGLE_OAUTH2_KEY="test-google-client",
    SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET="test-google-secret",
    SOCIAL_AUTH_FACEBOOK_KEY="test-facebook-client",
    SOCIAL_AUTH_FACEBOOK_SECRET="test-facebook-secret",
)
class SocialLoginTests(TestCase):
    def complete_google_callback(self):
        response = self.client.post(
            reverse("social:begin", args=["google-oauth2"]),
            {
                "next": "/forum/publications/",
            },
        )
        state = parse_qs(urlparse(response["Location"]).query)["state"][0]
        with (
            patch(
                "social_core.backends.google.GoogleOAuth2.request_access_token",
                return_value={
                    "access_token": "test-access-token",
                    "token_type": "Bearer",
                },
            ),
            patch(
                "social_core.backends.google.GoogleOAuth2.user_data",
                return_value={
                    "sub": "google-user-123",
                    "email": "google-user@example.com",
                    "email_verified": True,
                    "given_name": "Test",
                    "family_name": "User",
                },
            ),
        ):
            response = self.client.get(
                reverse("social:complete", args=["google-oauth2"]),
                {
                    "state": state,
                    "code": "test-code",
                },
            )
        return response

    def test_google_callback_runs_custom_pipeline_and_preserves_forum_destination(self):
        response = self.complete_google_callback()
        self.assertRedirects(response, "/forum/publications/", fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)
        association = UserSocialAuth.objects.get(provider="google-oauth2", uid="google-user-123")
        self.assertEqual(str(association.user_id), self.client.session["_auth_user_id"])

    def test_google_callback_preserves_existing_email_based_association(self):
        user = User.objects.create_user(email="google-user@example.com")
        association = UserSocialAuth.objects.create(
            user=user,
            provider="google-oauth2",
            uid=user.email,
            id_key="email",
            extra_data={"email": user.email},
        )
        response = self.complete_google_callback()
        self.assertRedirects(response, "/forum/publications/", fetch_redirect_response=False)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
        association.refresh_from_db()
        self.assertEqual(association.uid, "google-user-123")
        self.assertEqual(association.id_key, "sub")
        self.assertEqual(UserSocialAuth.objects.filter(user=user).count(), 1)

    def test_login_forms_start_oauth_with_csrf_and_preserve_next(self):
        for backend in ("google-oauth2", "facebook"):
            with self.subTest(backend=backend):
                client = Client(enforce_csrf_checks=True)
                next_url = "/forum/publications/?page=2&sort=new"
                response = client.get(reverse("pro_auth:login"), {"next": next_url})
                action = reverse("social:begin", args=[backend])
                form = next(
                    f for f in FormParser(response.content.decode()).forms if f["attrs"].get("action") == action
                )
                self.assertEqual(form["attrs"]["method"], "post")
                self.assertEqual(form["inputs"]["next"], next_url)
                self.assertTrue(form["inputs"]["csrfmiddlewaretoken"])

                self.assertEqual(client.get(action).status_code, 405)
                self.assertEqual(client.post(action, {"next": next_url}).status_code, 403)
                response = client.post(action, form["inputs"])
                self.assertEqual(response.status_code, 302)
                params = parse_qs(urlparse(response["Location"]).query)
                self.assertTrue(params["state"])
                self.assertEqual(client.session["next"], next_url)

    def test_comment_oauth_forms_preserve_article_path(self):
        request = RequestFactory().get("/articles/example/")
        request.user = AnonymousUser()
        html = render_to_string(
            "comment/comments/create_comment.html",
            {"user": request.user, "oauth": True, "login_url": "/login/"},
            request=request,
        )
        forms = FormParser(html).forms
        self.assertEqual(len(forms), 4)
        for form in forms:
            self.assertEqual(form["attrs"]["method"], "post")
            self.assertEqual(form["inputs"]["next"], request.path)
            self.assertTrue(form["inputs"]["csrfmiddlewaretoken"])
