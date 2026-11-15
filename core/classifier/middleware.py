from django.http import HttpResponsePermanentRedirect
from django.urls import get_script_prefix

from core.classifier.models import CategoryURLRedirect


class CategoryRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Leave service/API routes alone and avoid a redirect query on every request.
        match = request.resolver_match
        if request.method in ("GET", "HEAD") and match.url_name in ("parent-category-index", "posts-list-view"):
            language = getattr(request, "LANGUAGE_CODE", "")
            prefix = f"/{language}" if language and match.route.startswith(f"{language}/") else ""
            path = request.path_info[len(prefix) :] if prefix else request.path_info
            redirect = CategoryURLRedirect.objects.select_related("category").filter(old_path=path).first()
            if redirect and redirect.category.absolute_url != path:
                category = redirect.category
                if not category.get_ancestors(include_self=True).filter(is_active=False).exists():
                    target = get_script_prefix().rstrip("/") + prefix + category.absolute_url
                    if request.GET:
                        target += "?" + request.GET.urlencode()
                    return HttpResponsePermanentRedirect(target)
        return None
