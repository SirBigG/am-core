"""One write/preview policy for hub API and Admin; no public rendering."""

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from uuid import UUID

from django.conf import settings
from django.contrib.sites.models import Site
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.http import Http404

from core.classifier.models import CategoryHub
from core.classifier.publication_checks import SiteContentPolicy
from core.posts.models import GuideSectionArticle

from .access_models import RelationEntityGrant, RelationSiteGrant
from .block_models import BlockConfiguration, BlockConfigurationAudit, BlockConfigurationRevision, BlockManualPlacement
from .publication_eligibility import eligible_participant_urls, lock_publication_graph
from .relation_access import RelationAccess
from .relation_service import RelationConflict
from .selection import _spec, resolve_catalog_context, select_related_catalog
from .validation import validate_database_text

SALT = "catalog-block-activation-v1"
RULES = {
    "crop.related_preparations": {("plant_protection_application", "crop", "preparation")},
    "crop.related_problems": {("plant_protection_application", "crop", "target")},
    "crop.related_catalog": {("cultivar_of", "crop", "cultivar"), ("related_to", "member", "member")},
}
FIELDS = {
    "version",
    "slot",
    "title",
    "type",
    "context_role",
    "result_role",
    "filters",
    "conditions",
    "country_policy",
    "sort",
    "page_size",
    "empty",
    "presentation",
    "manual_replacement",
    "manual_ids",
}


def block_presets():
    base = dict(
        version=1,
        slot="crop.related_preparations",
        title="Препарати",
        type="plant_protection_application",
        context_role="crop",
        result_role="preparation",
        filters=["target", "method"],
        conditions={},
        country_policy="resolved_market",
        sort="canonical_title_uuid",
        page_size=12,
        empty="hide",
        presentation="catalog_cards",
        manual_replacement="none",
        manual_ids=[],
    )
    return [
        base,
        {**base, "slot": "crop.related_problems", "title": "Проблеми", "result_role": "target"},
        {
            **base,
            "slot": "crop.related_catalog",
            "title": "Сорти",
            "type": "cultivar_of",
            "result_role": "cultivar",
            "filters": [],
        },
    ]


def query_config(block):
    return {
        key: block[key] for key in ("version", "type", "context_role", "result_role", "filters", "sort", "page_size")
    }


def validate_blocks(blocks, *, schemas=True):
    validate_database_text(blocks)
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 3:
        raise ValidationError("Choose one to three ordered blocks.")
    slots, manual = set(), set()
    for b in blocks:
        if not isinstance(b, dict) or set(b) != FIELDS:
            raise ValidationError("Use exactly the documented block fields.")
        if (
            not isinstance(b["slot"], str)
            or b["slot"] not in RULES
            or b["slot"] in slots
            or not isinstance(b["title"], str)
            or not b["title"].strip()
            or len(b["title"]) > 200
            or not all(isinstance(b[k], str) for k in ("type", "context_role", "result_role"))
            or (b["type"], b["context_role"], b["result_role"]) not in RULES[b["slot"]]
            or b["country_policy"] != "resolved_market"
            or b["empty"] != "hide"
            or b["presentation"] not in ("catalog_cards", "catalog_list")
            or b["manual_replacement"] not in ("none", "guide_placements")
            or not isinstance(b["manual_ids"], list)
            or len(b["manual_ids"]) > 50
            or any(not isinstance(i, int) or isinstance(i, bool) or i <= 0 for i in b["manual_ids"])
            or len(set(b["manual_ids"])) != len(b["manual_ids"])
            or (b["manual_replacement"] == "none" and b["manual_ids"])
            or (b["manual_replacement"] == "guide_placements" and not b["manual_ids"])
            or manual.intersection(b["manual_ids"])
            or not isinstance(b["conditions"], dict)
        ):
            raise ValidationError("Invalid or incompatible declarative block parameters.")
        if schemas:
            _spec(query_config(b), b["conditions"])
        else:
            # The selector revalidates query fields/roles before any read.
            if not isinstance(b["filters"], list) or not isinstance(b["page_size"], int):
                raise ValidationError("Invalid query configuration.")
        slots.add(b["slot"])
        manual.update(b["manual_ids"])
    if len(manual) > 50:
        raise ValidationError("At most fifty manual placements per configuration.")
    return copy.deepcopy(blocks)


def _digest(value):
    # Preview cursors are timestamp-signed transport tokens. Bind whether
    # there is a next page, not the time the token was serialized.
    projection = copy.deepcopy(value)
    for block in projection["blocks"]:
        selection = block["selection"]
        selection["next_cursor"] = bool(selection["next_cursor"])
    return hashlib.sha256(json.dumps(projection, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _version(configuration, expected):
    if not isinstance(expected, int) or isinstance(expected, bool) or configuration.lock_version != expected:
        raise RelationConflict("Stale configuration; reload and preview again.")


@dataclass(frozen=True)
class BlockAccess:
    actor: object
    site_id: int

    def _grant(self, action="view", lock=False):
        if not getattr(self.actor, "is_authenticated", False):
            raise PermissionDenied("Authentication required.")
        # Refresh permissions on every action, including signed-preview replay.
        self.actor.refresh_from_db(fields=["is_active", "is_staff", "is_superuser"])
        for key in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            self.actor.__dict__.pop(key, None)
        if (
            not self.site_id
            or not self.actor.is_active
            or not self.actor.is_staff
            or not self.actor.has_perm("catalog.view_blockconfiguration")
            or not self.actor.has_perm("classifier.view_categoryhub")
            or not self.actor.has_perm("classifier.view_category")
            or (
                action != "view"
                and (
                    not self.actor.has_perm(f"catalog.{action}_blockconfiguration")
                    or not self.actor.has_perm("classifier.change_categoryhub")
                )
            )
        ):
            raise PermissionDenied("Scoped block configuration access is unavailable.")
        qs = RelationSiteGrant.objects.filter(actor=self.actor, site_id=self.site_id)
        if lock:
            lock_publication_graph()
            qs = qs.select_for_update()
        if action != "view":
            qs = qs.filter(**{"can_publish" if action == "publish" else "can_edit": True})
        grant = qs.first()
        if grant is None:
            raise PermissionDenied("Scoped block configuration access is unavailable.")
        if lock:
            list(
                RelationEntityGrant.objects.select_for_update()
                .filter(grant=grant)
                .order_by("pk")
                .values_list("pk", flat=True)
            )
        return grant

    def _hub(self, hub_id, locale, grant, lock=False):
        validate_database_text(locale)
        query = CategoryHub.objects.select_related("category")
        if lock:
            query = query.select_for_update(of=("self",))
        try:
            hub = query.get(pk=hub_id)
        except (CategoryHub.DoesNotExist, ValueError, TypeError) as exc:
            raise Http404("Hub unavailable.") from exc
        if (
            not isinstance(locale, str)
            or not re.fullmatch(r"[A-Za-z0-9-]{1,35}", locale)
            or hub.site_id not in (None, self.site_id)
            or hub.locale not in ("", locale)
            or not hub.category.entity_id
            or not SiteContentPolicy.objects.filter(site_id=self.site_id, content_locales__contains=[locale]).exists()
            or not RelationAccess(self.actor, self.site_id)
            ._participants(grant)
            .filter(entity_id=hub.category.entity_id, entity__kind="crop")
            .exists()
        ):
            raise Http404("Hub scope unavailable.")
        return hub

    def _configuration(self, hub, locale, lock=False):
        qs = BlockConfiguration.objects.filter(
            hub=hub, site_id=self.site_id, content_locale=locale, owner_id=hub.category.entity_id
        )
        if lock:
            qs = qs.select_for_update()
        return qs.first()

    def _conditions(self, grant, blocks, hub, *, historical=False):
        for b in blocks:
            ids = {k: v for k, v in b["conditions"].items() if isinstance(v, list)}
            requested = {UUID(str(value)) for values in ids.values() for value in values}
            available = set(
                RelationAccess(self.actor, self.site_id)
                ._participants(grant)
                .filter(entity_id__in=requested)
                .values_list("entity_id", flat=True)
            )
            if requested != available:
                raise PermissionDenied("A fixed participant is outside the current granted scope.")
        manual_ids = {i for b in blocks for i in b["manual_ids"]}
        if not manual_ids:
            return []
        if not all(
            self.actor.has_perm(p)
            for p in ("posts.view_post", "posts.view_guidesection", "posts.view_guidesectionarticle")
        ):
            raise PermissionDenied("Manual replacement requires visibility of guide placements and posts.")
        manual_query = GuideSectionArticle.objects.filter(pk__in=manual_ids)
        if not historical:
            manual_query = manual_query.filter(section__category_id=hub.guide_category_id or hub.category_id)
        rows = list(
            manual_query.order_by("pk").values(
                "id", "post_id", "section_id", "sort_order", "section__is_active", "section__category_id"
            )
        )
        if {row["id"] for row in rows} != manual_ids:
            raise ValidationError("A selected manual placement is unavailable in this guide scope.")
        return rows

    @transaction.atomic
    def read(self, hub_id, locale):
        grant = self._grant()
        hub = self._hub(hub_id, locale, grant)
        config = self._configuration(hub, locale)
        if config:
            # History is not an escape from current explicit participant scope.
            for revision in config.revisions.all():
                self._conditions(grant, revision.blocks, hub, historical=True)
        return config

    @transaction.atomic
    def save(self, hub_id, locale, blocks, expected_version):
        grant = self._grant("add" if expected_version is None else "change", lock=True)
        hub = self._hub(hub_id, locale, grant, lock=True)
        config = self._configuration(hub, locale, lock=True)
        if config:
            for old in config.revisions.all():
                self._conditions(grant, old.blocks, hub, historical=True)
            _version(config, expected_version)
        elif expected_version is not None:
            raise RelationConflict("Configuration no longer matches its base.")
        blocks = validate_blocks(blocks)
        self._conditions(grant, blocks, hub)
        if config is None:
            config = BlockConfiguration.objects.create(
                hub=hub,
                site_id=self.site_id,
                content_locale=locale,
                owner_id=hub.category.entity_id,
                created_by=self.actor,
            )
        revision = BlockConfigurationRevision.objects.create(
            configuration=config,
            number=(config.revisions.aggregate(last=Max("number"))["last"] or 0) + 1,
            blocks=blocks,
            created_by=self.actor,
        )
        for b in blocks:
            BlockManualPlacement.objects.bulk_create(
                [BlockManualPlacement(revision=revision, slot=b["slot"], placement_id=i) for i in b["manual_ids"]]
            )
        base = config.lock_version
        config.lock_version += 1
        config.save(update_fields=["lock_version"])
        BlockConfigurationAudit.objects.create(
            configuration=config, revision=revision, actor=self.actor, action="draft", base_version=base
        )
        return config

    def _plan(self, hub_id, locale, revision_id, country, *, action="view", lock=False):
        grant = self._grant(action, lock=lock)
        hub = self._hub(hub_id, locale, grant, lock=lock)
        config = self._configuration(hub, locale, lock=lock)
        if not config:
            raise Http404("Configuration unavailable.")
        try:
            revision = config.revisions.get(pk=revision_id)
        except (BlockConfigurationRevision.DoesNotExist, ValueError, TypeError, ValidationError) as exc:
            raise Http404("Revision unavailable.") from exc
        for old in config.revisions.all():
            self._conditions(grant, old.blocks, hub, historical=True)
        blocks = validate_blocks(revision.blocks)
        manual = self._conditions(grant, blocks, hub)
        if not hub.is_active:
            raise ValidationError("Activate the owning hub before previewing its blocks.")
        eligible_participant_urls(site_id=self.site_id, content_locale=locale, entity_ids=[config.owner_id])
        context = resolve_catalog_context(
            site=Site(pk=self.site_id), content_locale=locale, country=country, page_entity=config.owner_id
        )
        result = [
            {
                "slot": b["slot"],
                "title": b["title"],
                "presentation": b["presentation"],
                "manual_replacement": b["manual_replacement"],
                "manual_ids": b["manual_ids"],
                "selection": select_related_catalog(context, query_config(b), filters=b["conditions"]),
            }
            for b in blocks
        ]
        return (
            config,
            revision,
            dict(
                blocks=result,
                manual_manifest=manual,
                hub_state={
                    "updated": hub.updated.isoformat(),
                    "guide_category_id": hub.guide_category_id,
                    "owner": str(config.owner_id),
                },
            ),
        )

    @transaction.atomic
    def preview(self, hub_id, locale, revision_id, country):
        config, revision, result = self._plan(hub_id, locale, revision_id, country)
        token = signing.dumps(
            dict(
                actor=self.actor.pk,
                site=self.site_id,
                hub=config.hub_id,
                locale=locale,
                configuration=str(config.pk),
                version=config.lock_version,
                revision=str(revision.pk),
                country=country,
                plan_digest=_digest(result),
            ),
            salt=SALT,
            compress=True,
        )
        return {
            **result,
            "preview": token,
            "configuration_id": str(config.pk),
            "lock_version": config.lock_version,
            "revision_id": str(revision.pk),
            "country": country,
        }

    @transaction.atomic
    def activate(self, hub_id, locale, expected_version, preview):
        if not isinstance(preview, str):
            raise ValidationError("A signed reviewed preview is required.")
        try:
            token = signing.loads(preview, salt=SALT, max_age=getattr(settings, "CATALOG_BLOCK_PREVIEW_MAX_AGE", 900))
        except signing.BadSignature as exc:
            raise RelationConflict("Preview expired or invalid; preview again.") from exc
        if (
            token["actor"] != self.actor.pk
            or token["site"] != self.site_id
            or token["hub"] != hub_id
            or token["locale"] != locale
        ):
            raise PermissionDenied("Preview belongs to another actor or scope.")
        config, revision, plan = self._plan(
            hub_id, locale, token["revision"], token["country"], action="publish", lock=True
        )
        _version(config, expected_version)
        if (
            token["configuration"] != str(config.pk)
            or token["version"] != config.lock_version
            or token["plan_digest"] != _digest(plan)
        ):
            raise RelationConflict("Preview state changed; review a new preview.")
        base = config.lock_version
        config.active_revision = revision
        config.enabled = True
        config.lock_version += 1
        config.save(update_fields=["active_revision", "enabled", "lock_version"])
        BlockConfigurationAudit.objects.create(
            configuration=config, revision=revision, actor=self.actor, action="activate", base_version=base
        )
        return config

    @transaction.atomic
    def disable(self, hub_id, locale, expected_version):
        grant = self._grant("publish", lock=True)
        hub = self._hub(hub_id, locale, grant, lock=True)
        config = self._configuration(hub, locale, lock=True)
        if not config:
            raise Http404("Configuration unavailable.")
        for old in config.revisions.all():
            self._conditions(grant, old.blocks, hub, historical=True)
        _version(config, expected_version)
        base = config.lock_version
        config.enabled = False
        config.lock_version += 1
        config.save(update_fields=["enabled", "lock_version"])
        BlockConfigurationAudit.objects.create(
            configuration=config, revision=config.active_revision, actor=self.actor, action="disable", base_version=base
        )
        return config


def active_block_configuration(context, hub_id):
    """Find the current configuration for a trusted crop context."""
    from .selection import _CONTEXT, CatalogContext

    if not isinstance(context, CatalogContext) or context._verified is not _CONTEXT:
        raise ValidationError("Resolved context required.")
    config = (
        BlockConfiguration.objects.select_related("hub__category", "active_revision")
        .filter(
            hub_id=hub_id,
            site_id=context.site_id,
            content_locale=context.content_locale,
            owner_id=context.page_entity,
            enabled=True,
            hub__is_active=True,
        )
        .first()
    )
    if (
        not config
        or config.hub.category.entity_id != config.owner_id
        or config.hub.site_id not in (None, context.site_id)
        or config.hub.locale not in ("", context.content_locale)
    ):
        return None
    return config


def select_configured_blocks(context, hub_id, *, filters=None, cursors=None):
    config = active_block_configuration(context, hub_id)
    if not config:
        return []
    blocks = validate_blocks(config.active_revision.blocks, schemas=False)
    filters, cursors = {} if filters is None else filters, {} if cursors is None else cursors
    slots = {b["slot"] for b in blocks}
    if not isinstance(filters, dict) or not isinstance(cursors, dict) or set(filters) - slots or set(cursors) - slots:
        raise ValidationError("Unknown block filter/cursor scope.")
    result = []
    for b in blocks:
        selected = copy.deepcopy(b["conditions"])
        runtime = filters.get(b["slot"], {})
        if not isinstance(runtime, dict):
            raise ValidationError("Block filters must be objects.")
        for key, value in runtime.items():
            if key in selected and value != selected[key]:
                raise ValidationError("Runtime filter cannot replace a fixed condition.")
            selected[key] = value
        page = select_related_catalog(context, query_config(b), filters=selected, cursor=cursors.get(b["slot"]))
        result.append(
            {
                "slot": b["slot"],
                "visible": bool(page["count"]),
                "title": b["title"],
                "presentation": b["presentation"],
                "manual_replacement": b["manual_replacement"],
                "manual_ids": b["manual_ids"],
                "selection": page,
            }
        )
    return result
