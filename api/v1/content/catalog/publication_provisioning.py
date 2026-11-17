from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.catalog.publication_eligibility import _canonical, eligible_participant_urls
from core.catalog.relation_access import RelationAccess
from core.catalog.relation_service import set_presentation_selection
from core.catalog.relations import EntityPresentationSelection
from core.classifier.models import Category
from core.classifier.publication_checks import SiteCategoryConfiguration, SiteContentPolicy
from core.companies.models import Product, RelatedOfferPublication
from core.posts.models import Post
from core.posts.publication_checks import PostPublicationApproval, SitePostPublication, material_digest

from ..management import audit
from .provisioning import CatalogOperatorView
from .serializers import StrictSerializer
from .views import CatalogError


class PublicationPost(StrictSerializer):
    id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    digest = serializers.RegexField(r"^[a-f0-9]{64}$")


class PublicationOffer(StrictSerializer):
    id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    package_label = serializers.CharField(max_length=200)


class PublicationManifest(StrictSerializer):
    site_grant_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    content_locale = serializers.RegexField(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$", max_length=35)
    category_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=2**63 - 1), max_length=20, allow_empty=False
    )
    posts = PublicationPost(many=True, max_length=30)
    offers = PublicationOffer(many=True, max_length=30)
    review_reference = serializers.CharField(max_length=1000)

    def validate(self, data):
        for field in ("category_ids", "posts", "offers"):
            ids = data[field] if field == "category_ids" else [row["id"] for row in data[field]]
            if len(ids) != len(set(ids)):
                raise serializers.ValidationError({field: "Duplicate IDs are not allowed."})
        if data["content_locale"] == "und":
            raise serializers.ValidationError({"content_locale": "Choose the verified language of the material."})
        return data


def ensure_row(request, model, lookup, values):
    row, created = model.objects.get_or_create(**lookup, defaults=values)
    if created:
        audit(request, row, ADDITION)
    elif any(getattr(row, field) != value for field, value in values.items()):
        raise CatalogError(
            409, "publication_conflict", f"Existing {model._meta.verbose_name} differs from the manifest."
        )
    return row


class PublicationProvisioningView(CatalogOperatorView):
    @transaction.atomic
    def post(self, request):
        serializer = PublicationManifest(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        grant = self.lock_operator_scope(request, data["site_grant_id"])
        if not grant.can_publish:
            raise PermissionDenied("The site grant needs publication authority.")
        site_id, locale = grant.site_id, data["content_locale"]
        now = timezone.now()
        categories = Category.objects.in_bulk(data["category_ids"])
        post_digests = {row["id"]: row["digest"] for row in data["posts"]}
        posts = Post.objects.select_for_update().filter(pk__in=post_digests).in_bulk()
        if set(categories) != set(data["category_ids"]) or set(posts) != set(post_digests):
            raise CatalogError(404, "anchor_unavailable", "A requested category or post is unavailable.")
        anchors = [*categories.values(), *posts.values()]
        entity_ids = {anchor.entity_id for anchor in anchors}
        access = RelationAccess(grant.actor, site_id)
        granted = set(access._participants(grant).filter(entity__state="active").values_list("entity_id", flat=True))
        if not entity_ids <= granted or len(entity_ids) != len(anchors):
            raise CatalogError(409, "anchor_scope_conflict", "Each anchor needs a distinct active granted entity.")
        for post in posts.values():
            if (
                not post.status
                or post.publish_date > now
                or not _canonical(post.absolute_url)
                or material_digest(post) != post_digests[post.pk]
            ):
                raise CatalogError(
                    409, "post_review_conflict", f"Post {post.pk} differs from the reviewed public material."
                )

        policy, created = SiteContentPolicy.objects.get_or_create(
            site_id=site_id, defaults={"active": True, "content_locales": [locale]}
        )
        if created:
            audit(request, policy, ADDITION)
        elif not policy.active or not isinstance(policy.content_locales, list):
            raise CatalogError(409, "site_policy_conflict", "The existing site content policy must be reviewed.")
        elif locale not in policy.content_locales:
            policy.content_locales = [*policy.content_locales, locale]
            policy.save(update_fields=["content_locales"])
            audit(request, policy, CHANGE, ("content_locales",))

        rubrics = Category.objects.in_bulk({post.rubric_id for post in posts.values()})
        for category in [*categories.values(), *rubrics.values()]:
            for ancestor in category.get_ancestors(include_self=True):
                path = f"/{ancestor.slug}/" if ancestor.is_root_node() else ancestor.absolute_url
                if not ancestor.is_active or not _canonical(path):
                    raise CatalogError(409, "category_unavailable", f"Category {ancestor.pk} is unavailable.")
                ensure_row(
                    request,
                    SiteCategoryConfiguration,
                    {"site_id": site_id, "category_id": ancestor.pk, "content_locale": locale},
                    {"visible": True, "canonical_path": path},
                )
        for post in posts.values():
            self.provision_post(request, post, site_id, locale, now, data["review_reference"], post_digests[post.pk])

        for anchor in anchors:
            selection = EntityPresentationSelection.objects.filter(
                site_id=site_id, content_locale=locale, entity_id=anchor.entity_id
            ).first()
            post_id, category_id = (anchor.pk, None) if isinstance(anchor, Post) else (None, anchor.pk)
            if selection is None:
                set_presentation_selection(
                    site=grant.site,
                    content_locale=locale,
                    entity=anchor.entity,
                    anchor=anchor,
                    expected_version=None,
                    actor=request.user,
                    approved=True,
                )
            elif (selection.post_id, selection.category_id, selection.approved) != (post_id, category_id, True):
                raise CatalogError(409, "presentation_conflict", "The existing presentation differs from the manifest.")
        paths = eligible_participant_urls(site_id=site_id, content_locale=locale, entity_ids=entity_ids, lock=True)
        offers = self.provision_offers(request, data["offers"], posts, site_id, locale)
        return Response(
            {
                "version": 1,
                "site_id": site_id,
                "content_locale": locale,
                "presentations": {str(entity): path for entity, path in paths.items()},
                "offer_ids": offers,
            }
        )

    @staticmethod
    def provision_post(request, post, site_id, locale, now, reference, digest):
        approval, created = PostPublicationApproval.objects.get_or_create(
            post=post,
            content_digest=digest,
            content_locale=locale,
            defaults={
                "reviewed_by": request.user,
                "reviewed_at": now,
                "language_verified": True,
                "provenance": {"reference": reference},
            },
        )
        if created:
            audit(request, approval, ADDITION)
        publication, published = SitePostPublication.objects.get_or_create(
            site_id=site_id,
            post=post,
            content_locale=locale,
            defaults={
                "approval": approval,
                "category_id": post.rubric_id,
                "canonical_path": post.absolute_url,
                "enabled": True,
                "publish_at": post.publish_date,
            },
        )
        if published:
            audit(request, publication, ADDITION)
        elif (
            not publication.enabled
            or publication.approval_id != approval.pk
            or publication.category_id != post.rubric_id
            or publication.canonical_path != post.absolute_url
        ):
            raise CatalogError(409, "publication_conflict", "The existing post publication differs from the manifest.")

    @staticmethod
    def provision_offers(request, rows, posts, site_id, locale):
        market = getattr(settings, "RELATED_CATALOG_MARKETS", {}).get(site_id)
        products = (
            Product.objects.select_for_update(of=("self",))
            .select_related("company")
            .filter(pk__in=[row["id"] for row in rows])
            .in_bulk()
        )
        result = {}
        for row in rows:
            product = products.get(row["id"])
            if (
                not market
                or not product
                or product.post_id not in posts
                or not product.active
                or not product.company.active
                or product.match_status != Product.MatchStatus.CONFIRMED
            ):
                raise CatalogError(409, "offer_scope_conflict", f"Offer {row['id']} has no eligible confirmed match.")
            publication = ensure_row(
                request,
                RelatedOfferPublication,
                {"product_id": product.pk, "site_id": site_id, "country": market, "content_locale": locale},
                {
                    "post_id": product.post_id,
                    "entity_id": posts[product.post_id].entity_id,
                    "package_label": row["package_label"],
                    "enabled": True,
                },
            )
            result[str(product.pk)] = publication.pk
        return result
