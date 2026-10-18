from urllib.parse import urlencode

from django.conf import settings
from django.http import Http404
from django.utils.cache import add_never_cache_headers
from django.views.generic import ListView

from core.posts.models import SearchStatistic

from .inputs import clean_query
from .models import ResourceType, SearchDocument, SearchIndexState
from .query import result_counts, search_documents
from .sources import hydrate_market


class UnifiedSearchView(ListView):
    paginate_by = 20
    template_name = "search/results.html"

    def dispatch(self, request, *args, **kwargs):
        if not settings.UNIFIED_SEARCH_ENABLED:
            from core.posts.views import PostSearchView

            response = PostSearchView.as_view()(request, *args, **kwargs)
        else:
            response = super().dispatch(request, *args, **kwargs)
        add_never_cache_headers(response)
        return response

    def get_queryset(self):
        self.query = clean_query(self.request.GET.get("q", ""))
        self.kind = self.request.GET.get("type", "")
        self.archive = self.request.GET.get("archive") == "1"
        if self.kind and self.kind not in ResourceType.values:
            raise Http404("Unknown search resource type")
        self.ready = SearchIndexState.objects.filter(pk=1, active_generation__isnull=False).exists()
        matches = search_documents(self.query, archive=self.archive) if self.query else SearchDocument.objects.none()
        self.counts = result_counts(matches) if self.query else {}
        # Page/filter navigation is not a new search. Do not invent fingerprints.
        if self.query and not any(key in self.request.GET for key in ("page", "type", "archive")):
            SearchStatistic.objects.create(fingerprint="", search_phrase=self.query)
        return matches.filter(resource_type=self.kind) if self.kind else matches

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = context["page_obj"]
        page.object_list = hydrate_market(list(page.object_list))
        context["object_list"] = page.object_list
        params = {"q": self.query}
        if self.archive:
            params["archive"] = "1"
        filters = [("", "Усе", sum(self.counts.values()))]
        filters.extend((kind.value, kind.label, self.counts.get(kind.value, 0)) for kind in ResourceType)
        context.update(
            query=self.query,
            selected_type=self.kind,
            archive=self.archive,
            search_ready=self.ready,
            filters=[
                {
                    "label": label,
                    "count": count,
                    "active": kind == self.kind,
                    "url": "?" + urlencode(params | ({"type": kind} if kind else {})),
                }
                for kind, label, count in filters
            ],
            previous_url=(
                "?" + urlencode(params | {"type": self.kind, "page": page.previous_page_number()})
                if page.has_previous()
                else ""
            ),
            next_url=(
                "?" + urlencode(params | {"type": self.kind, "page": page.next_page_number()})
                if page.has_next()
                else ""
            ),
        )
        return context
