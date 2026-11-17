"""Fresh seller offers for a verified public relation selection."""

from decimal import Decimal
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Count, Exists, F, OuterRef, Q
from django.db.models.functions import Lower, Trim
from django.urls import reverse
from django.utils import timezone

from core.catalog.relations import EntityPresentationSelection

from .market import market_offers
from .models import CurrencyChoices, Product, RelatedOfferPublication

SALT = "related-catalog-offers-v1"


def matching_offer_publications(context):
    return RelatedOfferPublication.objects.filter(
        product_id=OuterRef("pk"),
        post_id=OuterRef("post_id"),
        entity_id=OuterRef("post__entity_id"),
        enabled=True,
        site_id=context.site_id,
        content_locale=context.content_locale,
        country=context.country,
    )


def related_offers(context, cards):
    """Select only explicit offer memberships for the accepted card anchors."""
    if context.site_id != getattr(settings, "SITE_ID", None):
        return Product.objects.none()
    anchors = Q()
    for card in cards:
        if card["kind"] != "crop":
            anchors |= Q(post__entity_id=card["id"], post__absolute_url=card["url"])
    if not anchors:
        return Product.objects.none()
    now = timezone.now()
    max_stored_price = Decimal("99999999.99")
    presentations = EntityPresentationSelection.objects.filter(
        post_id=OuterRef("post_id"),
        entity_id=OuterRef("post__entity_id"),
        approved=True,
        site_id=context.site_id,
        content_locale=context.content_locale,
    )
    return (
        market_offers()
        .filter(
            anchors,
            Exists(matching_offer_publications(context)),
            Exists(presentations),
            post__entity__state="active",
            post__publish_date__lte=now,
            price_updated_at__lte=now,
            currency__in=CurrencyChoices.values,
        )
        .alias(offer_name=Lower(Trim("name")), exact_name=Lower(Trim("post__title")))
        .filter(
            Q(match_status=Product.MatchStatus.CONFIRMED)
            | Q(post__entity__kind="cultivar", match_status=Product.MatchStatus.AUTO, offer_name=F("exact_name"))
        )
        .filter(
            Q(price__gt=0, price__lte=max_stored_price)
            | (
                Q(price__isnull=True, min_price__gt=0, min_price__lte=max_stored_price)
                & (Q(max_price__isnull=True) | Q(max_price__gte=F("min_price"), max_price__lte=max_stored_price))
            )
        )
    )


def related_offer_counts(context, cards):
    rows = (
        related_offers(context, cards)
        .order_by()
        .values("post__entity_id")
        .annotate(
            offers=Count("pk"),
            sellers=Count("company_id", distinct=True),
        )
    )
    return {str(row["post__entity_id"]): {"offers": row["offers"], "sellers": row["sellers"]} for row in rows}


def offer_link(context, *, anchor_type, anchor_id, query, block, card):
    selection = signing.dumps(
        {
            "site": context.site_id,
            "locale": context.content_locale,
            "country": context.country,
            "anchor_type": anchor_type,
            "anchor_id": anchor_id,
            "query": query,
            "block": block["index"],
            "revision": block["offer_scope"],
            "card": card["id"],
        },
        salt=SALT,
        compress=True,
    )
    return reverse("market:related-offers") + "?" + urlencode({"selection": selection})


def seller_url(value):
    if not value:
        return None
    try:
        URLValidator(schemes=["http", "https"])(value)
        if urlsplit(value).username is not None:
            return None
    except (ValidationError, ValueError):
        return None
    return value


def attach_related_offers(context, blocks, *, anchor_type, anchor_id, query):
    """Enrich eligible cards once across all visible blocks."""
    cards = [card for block in blocks for card in block["selection"]["results"]]
    counts = related_offer_counts(context, cards)
    for block in blocks:
        for card in block["selection"]["results"]:
            totals = counts.get(card["id"])
            if totals:
                card["market"] = {
                    **totals,
                    "url": offer_link(
                        context, anchor_type=anchor_type, anchor_id=anchor_id, query=query, block=block, card=card
                    ),
                }
            elif card["kind"] in {"preparation", "cultivar"}:
                card["market"] = {"offers": 0, "sellers": 0, "url": None}
