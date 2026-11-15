from django.conf import settings
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.generic import DetailView, ListView, TemplateView

from core.classifier.models import Category, Region
from core.posts.category_attributes import get_public_category_attribute_groups
from core.posts.crop_hub import hub_market_categories
from core.posts.crop_prices import build_price_overview, current_price_ranges

from .market import (
    crop_market_offers,
    market_categories,
    market_offers,
    market_posts,
    requested_crop_hub,
    summarize_offers,
)
from .models import CurrencyChoices, MarketPage, Product


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


def scoped_offers(crop_hub, region=""):
    offers = crop_market_offers(*crop_hub) if crop_hub else market_offers()
    return offers.filter(company__location__region_id=region) if region else offers


def picker_varieties(offers, slug):
    if not slug:
        return []
    return list(market_posts(offers=offers).filter(rubric__slug=slug).values("id", "title"))


@require_GET
def market_variety_options(request):
    crop_hub = requested_crop_hub(request)
    return JsonResponse({"varieties": picker_varieties(scoped_offers(crop_hub, selected_region(request)), request.GET.get("category", ""))})


def picker_context(crop_hub, offers, category, categories=None):
    if categories is None:
        categories = category_navigation()
        if crop_hub:
            allowed = set(hub_market_categories(*crop_hub).values_list("pk", flat=True))
            categories = [item for item in categories if item.pk in allowed]
    return {
        "categories": categories,
        "category": category,
        "picker_varieties": picker_varieties(offers, category.slug if category else ""),
    }


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
            variety = query.pop("variety", [""])[0]
            if slug and variety:
                if not variety.isascii() or not variety.isdecimal() or len(variety) > 18:
                    raise Http404("Unknown variety")
                offers = scoped_offers(requested_crop_hub(request), selected_region(request))
                post = get_object_or_404(market_posts(offers=offers), pk=variety, rubric=category)
                url = reverse("market:variety", args=[post.pk])
            if not query.get("region"):
                query.pop("region", None)
            return redirect(url + ("?" + query.urlencode() if query else ""))
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        self.category = None
        self.crop_hub = requested_crop_hub(self.request)
        self.offers = scoped_offers(self.crop_hub, selected_region(self.request))
        queryset = market_posts(offers=self.offers)
        if "slug" in self.kwargs:
            self.category = get_object_or_404(Category, slug=self.kwargs["slug"], is_active=True)
            queryset = queryset.filter(rubric=self.category)
        self.search = self.request.GET.get("q", "").strip()[:160]
        self.sort = self.request.GET.get("sort", "")
        if self.search:
            queryset = queryset.filter(title__icontains=self.search)
        if self.sort in {"offers", "price"}:
            product_rows = Product.objects.filter(pk__in=self.offers.values("pk"), post_id=OuterRef("pk"))
            if self.sort == "offers":
                counts = product_rows.order_by().values("post_id").annotate(total=Count("pk")).values("total")
                queryset = queryset.annotate(offer_count=Subquery(counts)).order_by("-offer_count", "title", "pk")
            else:
                prices = product_rows.filter(currency=CurrencyChoices.UAH).annotate(
                    listed_price=Coalesce("price", "min_price")
                ).order_by("listed_price").values("listed_price")[:1]
                queryset = queryset.annotate(lowest_uah=Subquery(prices)).order_by(
                    F("lowest_uah").asc(nulls_last=True), "title", "pk"
                )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = MarketPage.objects.filter(category=self.category).first()
        label = (page.label if page else "") or (self.category.value if self.category else "Агромаркет")
        heading = (page.heading if page else "") or (
            f"{label}: пропозиції продавців" if self.category else "Агромаркет"
        )
        categories = category_navigation()
        if self.crop_hub:
            allowed = set(hub_market_categories(*self.crop_hub).values_list("pk", flat=True))
            categories = [item for item in categories if item.pk in allowed]
        if self.category and self.category.pk not in {item.pk for item in categories}:
            self.category.market_label = label
            categories.append(self.category)
        region_offers = crop_market_offers(*self.crop_hub) if self.crop_hub else market_offers()
        if self.category:
            region_offers = region_offers.filter(category=self.category)
        context.update(
            regions=Region.objects.filter(
                Q(pk__in=region_offers.values("company__location__region_id"))
                | Q(pk=self.request.GET.get("region") or None)
            ).order_by("value"),
            selected_region=self.request.GET.get("region", ""),
            selected_hub=self.request.GET.get("hub", ""),
            crop_hub_category=self.crop_hub[0] if self.crop_hub else None,
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
        context.update(picker_context(self.crop_hub, self.offers, self.category, categories))
        context.update(market_search=self.search, market_sort=self.sort)
        if self.category:
            offers = self.offers.filter(category=self.category)
            ranges = current_price_ranges(Product.objects.filter(pk__in=offers.values("pk")))
            labels = dict(CurrencyChoices.choices)
            for group in ranges:
                code = group["currency_code"]
                group["currency"] = labels.get(code, code) or "Валюта не вказана"
            context["market_ranges"] = ranges
        context["varieties"] = [summarize_offers(post) for post in context["varieties"]]
        return context


class MarketVarietyView(DetailView):
    template_name = "companies/market_variety.html"
    context_object_name = "variety"

    def get_queryset(self):
        crop_hub = requested_crop_hub(self.request)
        self.crop_hub = crop_hub
        self.offers = scoped_offers(crop_hub, selected_region(self.request))
        return market_posts(offers=self.offers)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        variety = summarize_offers(self.object)
        period = 90 if self.request.GET.get("period") == "90" else 30
        sort = self.request.GET.get("sort", "company")
        if sort in {"asc", "desc"}:
            variety.market_offers.sort(
                key=lambda offer: (offer.currency or "", offer.market_price_min * (-1 if sort == "desc" else 1))
            )
        context.update(picker_context(self.crop_hub, self.offers, variety.rubric))
        regions = scoped_offers(self.crop_hub).filter(post=variety).values("company__location__region_id")
        context.update(
            regions=Region.objects.filter(Q(pk__in=regions) | Q(pk=self.request.GET.get("region") or None)).order_by("value"),
            market_sort=sort,
            period=period,
            price_overview=build_price_overview(self.offers.filter(post=variety), timezone.now(), days=period),
            selected_region=self.request.GET.get("region", ""),
            market_tab="products",
            selected_hub=self.request.GET.get("hub", ""),
            crop_hub_category=self.crop_hub[0] if self.crop_hub else None,
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
