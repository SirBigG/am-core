"""Render a seller list only while the original public card remains eligible."""

from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.core.paginator import Paginator
from django.db.models import Subquery
from django.http import Http404, QueryDict
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from core.catalog.public_blocks import public_blocks
from core.classifier.models import Category
from core.posts.models import Post
from core.posts.templatetags.post_extras import public_url

from .related_offers import SALT, matching_offer_publications, related_offers, seller_url


@never_cache
@require_safe
def catalog_offers(request):
    if set(request.GET) - {"selection", "page"} or any(len(request.GET.getlist(key)) != 1 for key in request.GET):
        raise Http404
    token = request.GET.get("selection", "")
    if not token or len(token) > 16000:
        raise Http404
    try:
        scope = signing.loads(token, salt=SALT)
    except signing.BadSignature as exc:
        raise Http404 from exc
    if scope["site"] != getattr(settings, "SITE_ID", None):
        raise Http404
    model = {"category": Category, "post": Post}.get(scope["anchor_type"])
    if model is None:
        raise Http404
    anchor = get_object_or_404(model.objects.only("pk", "entity_id", "absolute_url"), pk=scope["anchor_id"])
    query = QueryDict(urlencode(scope["query"]))
    result = public_blocks(anchor, anchor.absolute_url, query, category=model is Category, strict=True)
    context = result.get("market_context")
    if (
        not context
        or result["error"]
        or (context.content_locale, context.country) != (scope["locale"], scope["country"])
    ):
        raise Http404
    card = next(
        (
            card
            for block in result["blocks"]
            if block["index"] == scope["block"] and block["offer_scope"] == scope["revision"]
            for card in block["selection"]["results"]
            if card["id"] == scope["card"]
        ),
        None,
    )
    if card is None:
        raise Http404
    # Preserve packages and prices per offer. No cross-currency price sort.
    offers = related_offers(context, [card]).order_by("company__name", "pk")
    seller_count = offers.values("company_id").distinct().order_by().count()
    offers = offers.annotate(package_label=Subquery(matching_offer_publications(context).values("package_label")[:1]))
    page = Paginator(offers, 20).get_page(request.GET.get("page", "1"))
    for offer in page:
        offer.seller_url = seller_url(offer.link)
    back = anchor.absolute_url + ("?" + urlencode(scope["query"]) if scope["query"] else "")
    response = render(
        request,
        "companies/catalog_offers.html",
        {
            "card": card,
            "offers": page,
            "seller_count": seller_count,
            "back": back + f"#related-catalog-{scope['block']}",
            "market_title": f"{card['title']} — пропозиції продавців",
            "publication_canonical_url": public_url(card["url"]),
        },
    )
    response["X-Robots-Tag"] = "noindex, follow"
    return response
