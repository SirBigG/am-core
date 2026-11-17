"""Public page adapters for the shared catalog selector."""

from dataclasses import dataclass
from urllib.parse import urlencode
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.crypto import salted_hmac

from core.classifier.models import CategoryHub

from .block_models import BlockConfiguration
from .blocks import active_block_configuration, query_config
from .publication_eligibility import eligible_participant_urls
from .relations import EntityPresentationSelection
from .selection import resolve_catalog_context, select_related_catalog

APPLICATION = "plant_protection_application"
PREPARATIONS = "crop.related_preparations"
PREFIX = "catalog_"
CURSOR_SALT = "public-catalog-page-v1"
FILTER_LABELS = {
    "target": "Проблема",
    "method": "Спосіб застосування",
    "crop": "Культура",
    "kind": "Вид матеріалу",
    "member": "Учасник зв’язку",
    "preparation": "Препарат",
    "cultivar": "Сорт",
}
METHOD_LABELS = {
    "foliar_spray": "Обприскування",
    "soil_application": "Ґрунтове внесення",
    "seed_treatment": "Обробка насіння",
}


@dataclass(frozen=True)
class PublicPage:
    site: object
    locale: str
    country: str
    entity: object

    def context(self, entity_id=None):
        return resolve_catalog_context(
            site=self.site, content_locale=self.locale, country=self.country, page_entity=entity_id or self.entity.pk
        )


def _page(anchor, path, *, category):
    site_id = getattr(settings, "SITE_ID", None)
    country = getattr(settings, "RELATED_CATALOG_MARKETS", {}).get(site_id)
    if not country or not anchor.entity_id or not path:
        return None
    selections = list(
        EntityPresentationSelection.objects.filter(
            site_id=site_id,
            entity_id=anchor.entity_id,
            approved=True,
            entity__state="active",
            **{"category_id" if category else "post_id": anchor.pk},
        ).select_related("site", "entity")[:2]
    )
    if len(selections) != 1:
        return None
    selection = selections[0]
    try:
        urls = eligible_participant_urls(
            site_id=site_id, content_locale=selection.content_locale, entity_ids=[anchor.entity_id]
        )
    except ValidationError:
        return None
    if urls[anchor.entity_id] != path:
        return None
    return PublicPage(selection.site, selection.content_locale, country, selection.entity)


def _query(params, *, strict):
    result = {}
    for key in params:
        if not key.startswith(PREFIX):
            if strict:
                raise ValidationError("Невідомий параметр.")
            continue
        values = params.getlist(key)
        if len(values) != 1 or len(values[0]) > 4096:
            raise ValidationError("Некоректне значення фільтра.")
        result[key] = values[0]
    return result


def _reverse(page, relation, role):
    config = dict(
        version=1,
        type=relation,
        context_role=role,
        result_role="crop",
        filters=[],
        sort="canonical_title_uuid",
        page_size=20,
    )
    return select_related_catalog(page.context(), config)


def _detail_rule(page, params):
    """Resolve a crop from released facts, then use that crop's saved rule."""
    kind = page.entity.kind
    roles = {"disease": "target", "pest": "target", "weed": "target", "preparation": "preparation"}
    cultivar = kind == "cultivar"
    if not cultivar and kind not in roles:
        return None, []
    found = _reverse(page, "cultivar_of" if cultivar else APPLICATION, "cultivar" if cultivar else roles[kind])
    # Limit the choice to a complete result. Never choose an arbitrary crop
    # or make a partial list look exhaustive.
    if found["next_cursor"] or (cultivar and found["count"] != 1):
        return None, []
    roots = {card["id"]: card for card in found["results"]}
    configurations = (
        BlockConfiguration.objects.filter(
            site=page.site,
            content_locale=page.locale,
            owner_id__in=roots,
            enabled=True,
            hub__is_active=True,
        )
        .filter(Q(hub__site_id=page.site.pk) | Q(hub__site__isnull=True))
        .filter(Q(hub__locale=page.locale) | Q(hub__locale=""))
        .select_related("hub__category", "active_revision")
    )
    candidates = {}
    for config in configurations.order_by("hub_id"):
        if config.hub.category.entity_id != config.owner_id:
            continue
        block = next((b for b in config.active_revision.blocks if b["slot"] == PREPARATIONS), None)
        if block:
            candidates[str(config.owner_id)] = (block, config)
    choices = [dict(id=key, label=card["title"]) for key, card in roots.items() if key in candidates]
    chosen = params.get("catalog_crop")
    if chosen and chosen not in candidates:
        raise ValidationError("Культура недоступна в цій добірці.")
    if not chosen and len(candidates) == 1:
        chosen = next(iter(candidates))
    if not chosen:
        return None, choices
    block, config = candidates[chosen]
    block = {**block, "manual_ids": []}
    conditions = dict(block["conditions"])
    selector = query_config(block)
    context = page.context(chosen)
    if cultivar:
        block["title"] = f"Для культури {roots[chosen]['title']}"
    elif kind == "preparation":
        if conditions.get("kind", "preparation") != "preparation":
            return None, choices
        conditions.pop("kind", None)
        selector["filters"] = [key for key in selector["filters"] if key != "kind"]
        if "preparation" in conditions and str(page.entity.pk) not in conditions["preparation"]:
            return None, choices
        if "crop" in conditions and chosen not in conditions["crop"]:
            return None, choices
        selector.update(context_role="preparation", result_role="crop")
        selector["filters"] = sorted(set(selector["filters"]) | {"crop"})
        conditions["crop"] = [chosen]
        context = page.context()
        block["title"] = "Застосування для " + roots[chosen]["title"]
    else:
        target = str(page.entity.pk)
        if "target" in conditions and target not in conditions["target"]:
            return None, choices
        selector["filters"] = sorted(set(selector["filters"]) | {"target"})
        conditions["target"] = [target]
    return (block, config, context, selector, conditions), choices


def _url(path, params):
    return path + ("?" + urlencode(params) if params else "")


def _selected_block(page, path, rule, params, index, allowed_keys):
    block, config, context, selector, conditions = rule
    prefix = f"catalog_{index}_"
    selected = dict(conditions)
    fields = []
    preserved = {}
    for key in selector["filters"]:
        if key not in FILTER_LABELS:
            continue
        name = prefix + key
        allowed_keys.add(name)
        value = params.get(name, "")
        if value:
            if key in {"method", "kind"}:
                narrowed = value
            else:
                try:
                    narrowed = [str(UUID(item)) for item in value.split(",")]
                except ValueError as exc:
                    raise ValidationError("Некоректне значення фільтра.") from exc
            if key in conditions:
                fixed = conditions[key]
                compatible = (
                    set(narrowed) <= {str(UUID(item)) for item in fixed}
                    if isinstance(fixed, list)
                    else narrowed == fixed
                )
                if not compatible:
                    raise ValidationError("Фільтр суперечить умовам добірки.")
            selected[key] = narrowed
            if key in conditions or (isinstance(narrowed, list) and len(narrowed) > 1):
                preserved[name] = value
                continue
        if key not in conditions:
            fields.append(dict(key=key, name=name, label=FILTER_LABELS[key], value=value))
    cursor_key = prefix + "page"
    allowed_keys.add(cursor_key)
    binding = [path, str(config.active_revision_id), block["slot"], context.page_entity, params.get("catalog_crop")]
    cursor = None
    if cursor_key in params:
        try:
            payload = signing.loads(params[cursor_key], salt=CURSOR_SALT)
            if payload["binding"] != binding or not isinstance(payload["cursor"], str):
                raise ValueError
            cursor = payload["cursor"]
        except (signing.BadSignature, KeyError, TypeError, ValueError) as exc:
            raise ValidationError("Сторінка добірки недоступна.") from exc
    result = select_related_catalog(context, selector, filters=selected, cursor=cursor)
    for field in fields:
        key = field.pop("key")
        field["options"] = result["facets"].get(key, [])
        if key == "kind":
            labels = {
                "crop": "Культура",
                "cultivar": "Сорт",
                "disease": "Хвороба",
                "pest": "Шкідник",
                "weed": "Бур’ян",
                "preparation": "Препарат",
            }
            kinds = sorted({card["kind"] for card in result["results"]})
            field["options"] = [{"id": kind, "label": labels[kind]} for kind in kinds]
        if field["name"].endswith("_method"):
            field["options"] = [
                {**option, "label": METHOD_LABELS.get(option["id"], option["label"])} for option in field["options"]
            ]
    next_url = None
    if result["next_cursor"]:
        next_params = {
            **params,
            cursor_key: signing.dumps({"binding": binding, "cursor": result["next_cursor"]}, salt=CURSOR_SALT),
        }
        next_url = _url(path, next_params) + f"#related-catalog-{index}"
    for card in result["results"]:
        card["method_labels"] = sorted(
            {
                METHOD_LABELS.get(detail["method_id"], detail["method_id"])
                for detail in card["details"]
                if "method_id" in detail
            }
        )
        card["href"] = card["url"]
        if context.page_entity != card["id"] and card["kind"] in {"preparation", "disease", "pest", "weed"}:
            crop = next(
                (
                    detail["participants"].get("crop", [None])[0]
                    for detail in card["details"]
                    if detail["participants"].get("crop")
                ),
                None,
            )
            if crop and card["id"] != str(page.entity.pk):
                link_params = {"catalog_crop": crop}
                if "method" in selected:
                    link_params["catalog_1_method"] = selected["method"]
                if card["kind"] == "preparation" and selected.get("target"):
                    link_params["catalog_1_target"] = ",".join(selected["target"])
                if card["kind"] in {"disease", "pest", "weed"} and selected.get("preparation"):
                    link_params["catalog_1_preparation"] = ",".join(selected["preparation"])
                card["href"] = _url(card["url"], link_params)
    return dict(
        index=index,
        offer_scope=salted_hmac("catalog-offer-scope", str(config.active_revision_id)).hexdigest(),
        title=block["title"],
        slot=block["slot"],
        presentation=block["presentation"],
        selection=result,
        fields=fields,
        preserved=preserved,
        next_url=next_url,
        filtered=any(params.get(f["name"]) for f in fields) or bool(cursor) or bool(preserved),
    )


def public_blocks(anchor, path, query, *, category=False, strict=False, include_offers=False):
    """Build the same projection for a public page and its JSON endpoint."""
    result = dict(blocks=[], crop_choices=[], selected_crop="", manual_ids=set(), error="", path=path)
    page = _page(anchor, path, category=category)
    if not page:
        return result
    result["market_context"] = page.context()
    try:
        rules = []
        if category:
            hub = CategoryHub.objects.filter(category=anchor).first()
            config = active_block_configuration(page.context(), hub.pk) if hub else None
            if config:
                for block in config.active_revision.blocks:
                    result["manual_ids"].update(block["manual_ids"])
                    rules.append((block, config, page.context(), query_config(block), block["conditions"]))
        params = _query(query, strict=strict)
        allowed_keys = set()
        if not category:
            allowed_keys.add("catalog_crop")
            rule, choices = _detail_rule(page, params)
            result.update(crop_choices=choices, selected_crop=params.get("catalog_crop", ""))
            if rule:
                rules.append(rule)
        blocks = [_selected_block(page, path, rule, params, index, allowed_keys) for index, rule in enumerate(rules, 1)]
        if set(params) - allowed_keys:
            raise ValidationError("Фільтр недоступний для цієї добірки.")
        result["blocks"] = [b for b in blocks if b["selection"]["results"] or b["filtered"]]
        if include_offers:
            from core.companies.related_offers import attach_related_offers

            attach_related_offers(
                result["market_context"],
                result["blocks"],
                anchor_type="category" if category else "post",
                anchor_id=anchor.pk,
                query=params,
            )
    except ValidationError:
        result["error"] = "Фільтр або сторінка добірки недоступні. Скиньте параметри й спробуйте знову."
    return result
