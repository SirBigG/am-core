from django.conf import settings
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView, ListView, TemplateView

from core.classifier.models import Category
from core.posts.category_attributes import get_public_category_attribute_groups

from .market import market_categories, market_posts, summarize_offers
from .models import MarketPage


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

    def get_queryset(self):
        self.category = None
        queryset = market_posts()
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
        context.update(
            category=self.category,
            categories=category_navigation(),
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
        return market_posts()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        variety = summarize_offers(self.object)
        context.update(
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
