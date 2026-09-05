from django.conf import settings
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView, ListView, TemplateView

from core.classifier.models import Category, Region
from core.posts.category_attributes import get_public_category_attribute_groups

from .market import market_categories, market_offers, market_posts, summarize_offers
from .models import MarketPage


def selected_region(request):
    value = request.GET.get("region", "")
    if value:
        if not value.isascii() or not value.isdecimal():
            raise Http404("Unknown region")
        get_object_or_404(Region, pk=value)
    return value


def category_navigation():
    labels = dict(MarketPage.objects.exclude(category=None).values_list("category_id", "label"))
    categories = list(market_categories())
    for category in categories:
        category.market_label = labels.get(category.pk) or category.value
    return categories


class MarketListView(ListView):
    template_name = "companies/market_list.html"
    context_object_name = "varieties"
    paginate_by = 24

    def get(self, request, *args, **kwargs):
        if "category" in request.GET:
            slug = request.GET["category"]
            if slug:
                category = get_object_or_404(Category, slug=slug, is_active=True)
                url = reverse("market:category", args=[category.slug])
            else:
                url = reverse("market:list")
            query = request.GET.copy()
            query.pop("category", None)
            query.pop("page", None)
            if not query.get("region"):
                query.pop("region", None)
            return redirect(url + ("?" + query.urlencode() if query else ""))
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        self.category = None
        queryset = market_posts(selected_region(self.request))
        if "slug" in self.kwargs:
            self.category = get_object_or_404(Category, slug=self.kwargs["slug"], is_active=True)
            queryset = queryset.filter(rubric=self.category)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = MarketPage.objects.filter(category=self.category).first()
        label = (page.label if page else "") or (self.category.value if self.category else "Агромаркет")
        heading = (page.heading if page else "") or (
            f"{label}: пропозиції продавців" if self.category else "Агромаркет"
        )
        categories = category_navigation()
        if self.category and self.category.pk not in {item.pk for item in categories}:
            self.category.market_label = label
            categories.append(self.category)
        region_offers = market_offers()
        if self.category:
            region_offers = region_offers.filter(category=self.category)
        context.update(
            regions=Region.objects.filter(
                Q(pk__in=region_offers.values("company__location__region_id"))
                | Q(pk=self.request.GET.get("region") or None)
            ).order_by("value"),
            selected_region=self.request.GET.get("region", ""),
            category=self.category,
            categories=categories,
            market_tab="products",
            market_heading=heading,
            market_title=(page.title if page else "") or f"{heading} — ціни та порівняння | AgroMega",
            market_description=(page.description if page else "")
            or f"{label}: порівнюйте ціни та пропозиції компаній за сортами каталогу AgroMega.",
            market_text=(page.text if page else ""),
            market_noindex=bool(self.request.GET) or context["paginator"].count == 0,
        )
        context["varieties"] = [summarize_offers(post) for post in context["varieties"]]
        return context


class MarketVarietyView(DetailView):
    template_name = "companies/market_variety.html"
    context_object_name = "variety"

    def get_queryset(self):
        return market_posts(selected_region(self.request))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        variety = summarize_offers(self.object)
        context.update(
            selected_region=self.request.GET.get("region", ""),
            market_tab="products",
            attributes=get_public_category_attribute_groups(variety),
            market_heading=f"{variety.title}: пропозиції продавців",
            market_title=f"{variety.title} — ціни та пропозиції | Агромаркет",
            market_description=f"Порівняйте пропозиції сорту {variety.title} від компаній. Характеристики з каталогу AgroMega, ціни для ознайомлення та посилання на продавців.",
            market_noindex=bool(self.request.GET),
        )
        return context


class MarketSitemapView(TemplateView):
    template_name = "companies/market_sitemap.xml"
    content_type = "application/xml"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paths = []
        if market_categories().exists():
            paths.append(reverse("market:list"))
        paths.extend(reverse("market:category", args=[c.slug]) for c in market_categories())
        paths.extend(reverse("market:variety", args=[pk]) for pk in market_posts().values_list("pk", flat=True))
        context["locations"] = [settings.HOST.rstrip("/") + path for path in paths]
        return context
