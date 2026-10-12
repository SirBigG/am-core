from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.http import Http404, HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from core.posts.views import PostDetail


class PostCanonicalRedirectTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.canonical = reverse("post-detail", args=("kartoplya", "hvoroby-kartopli", "parsha", 3926))
        self.post = SimpleNamespace(get_absolute_url=Mock(return_value=self.canonical))

    def response(self, path, method="get"):
        request = getattr(self.factory, method)(path)
        match = resolve(request.path)
        with (
            patch.object(PostDetail, "get_object", return_value=self.post) as get_object,
            patch.object(PostDetail, "get_context_data", return_value={}) as context,
            patch.object(PostDetail, "render_to_response", return_value=HttpResponse("article")) as render,
        ):
            response = match.func(request, **match.kwargs)
        get_object.assert_called_once_with()
        return response, context, render

    def test_old_category_redirects_directly_to_current_canonical(self):
        old = reverse("post-detail", args=("koreneplidni", "koreneplidni-user", "parsha", 3926))
        response, context, render = self.response(old)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["Location"], self.canonical)
        context.assert_not_called()
        render.assert_not_called()

    def test_obsolete_slug_redirects_to_canonical_without_query_parameters(self):
        old = reverse("post-detail", args=("kartoplya", "hvoroby-kartopli", "obsolete", 3926))
        response, _, _ = self.response(old + "?utm_source=legacy")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["Location"], self.canonical)

    def test_canonical_url_renders_without_redirect_loop(self):
        response, context, render = self.response(self.canonical + "?utm_source=test")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Location", response.headers)
        context.assert_called_once_with(object=self.post)
        render.assert_called_once_with({})

    def test_head_of_old_category_redirects(self):
        old = reverse("post-detail", args=("koreneplidni", "koreneplidni-user", "parsha", 3926))
        response, _, _ = self.response(old, method="head")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["Location"], self.canonical)

    def test_missing_post_remains_404(self):
        request = self.factory.get(self.canonical)
        match = resolve(request.path)
        with patch.object(PostDetail, "get_object", side_effect=Http404):
            with self.assertRaises(Http404):
                match.func(request, **match.kwargs)
