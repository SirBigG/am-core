"""Fresh public relation reads shared by page, API and preview consumers.

No result or candidate cache: the durable invalidation adapter is not
installed. The data query is one statement, so all eligibility evidence
has one MVCC snapshot.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.sites.models import Site
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

from core.posts.publication_checks import material_digest

from .models import CatalogEntityKind
from .publication_eligibility import _canonical
from .relations import RelationTypeVersion

_CONTEXT = object()
_SUPPORTED = {"related_to", "cultivar_of", "plant_protection_application"}
_SALT = "catalog-selection-cursor-v1"


@dataclass(frozen=True)
class CatalogContext:
    site_id: int
    content_locale: str
    country: str
    page_entity: str
    _verified: object


def resolve_catalog_context(*, site, content_locale, country, page_entity):
    """Use a Site selected by trusted routing/market policy, never a raw Host.

    Content language and country must come from that route's verified
    policy. UI language is not a substitute. The selector repeats live
    database policy.
    """
    if (
        not isinstance(site, Site)
        or not site.pk
        or not isinstance(content_locale, str)
        or not re.fullmatch(r"[A-Za-z0-9-]{1,35}", content_locale)
        or not isinstance(country, str)
        or not re.fullmatch(r"[A-Z]{2}", country)
    ):
        raise ValidationError("An explicit resolved site, content language and country are required.")
    return CatalogContext(site.pk, content_locale, country, _uuid(page_entity), _CONTEXT)


def _uuid(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("An explicit catalog UUID is required.") from exc


def _spec(config, filters):
    allowed = {"version", "type", "context_role", "result_role", "filters", "sort", "page_size"}
    if not isinstance(config, dict) or set(config) - allowed:
        raise ValidationError("Unknown selector configuration.")
    if (
        not isinstance(config.get("version"), int)
        or isinstance(config.get("version"), bool)
        or config["version"] != 1
        or not isinstance(config.get("type"), str)
        or config["type"] not in _SUPPORTED
        or config.get("sort") != "canonical_title_uuid"
        or not isinstance(config.get("page_size"), int)
        or isinstance(config.get("page_size"), bool)
        or not 1 <= config["page_size"] <= 20
        or not isinstance(config.get("filters"), list)
        or any(not isinstance(v, str) for v in config["filters"])
        or len(set(config["filters"])) != len(config["filters"])
        or not isinstance(config.get("context_role"), str)
        or not isinstance(config.get("result_role"), str)
        or not isinstance(filters, dict)
        or set(filters) - set(config["filters"])
    ):
        raise ValidationError("Invalid or unsupported selector scope/filter.")
    schemas = list(RelationTypeVersion.objects.filter(relation_type_id=config["type"]).values("roles"))
    roles = set.intersection(*(set(row["roles"]) for row in schemas)) if schemas else set()
    extra = {"kind"} | ({"method"} if config["type"] == "plant_protection_application" else set())
    if not {config["context_role"], config["result_role"]}.issubset(roles) or set(config["filters"]) - (roles | extra):
        raise ValidationError("Unknown or disallowed relation role/filter.")
    normalized = {}
    for key, value in filters.items():
        if key in roles:
            if not isinstance(value, list) or not 1 <= len(value) <= 50:
                raise ValidationError("Participant filters require one to fifty explicit UUIDs.")
            normalized[key] = sorted({_uuid(v) for v in value})
        elif key == "method":
            if not isinstance(value, str) or not re.fullmatch(r"[-a-zA-Z0-9_]{1,64}", value):
                raise ValidationError("Invalid method filter.")
            normalized[key] = value
        elif key == "kind":
            if value not in CatalogEntityKind.values:
                raise ValidationError("Unknown entity kind.")
            normalized[key] = value
    if sum(len(v) for v in normalized.values() if isinstance(v, list)) > 50:
        raise ValidationError("At most fifty participant UUIDs may be selected across filters.")
    return normalized


# All interpolated identifiers below are fixed application SQL, values are parameters.
# to_jsonb evidence is private intermediate data; only _card/public details escape.
_SQL = """
SELECT jsonb_build_object(
 'record_id', r.id, 'revision_id', v.id, 'payload', v.payload, 'source', v.source,
 'country', v.country, 'type', r.relation_type_id,
 'application', to_jsonb(d), 'country_policy', to_jsonb(cp),
 'method_active', m.active, 'withdrawn_at', w.occurred_at,
 'participants', (SELECT jsonb_agg(jsonb_build_object(
    'id', e.id, 'kind', e.kind, 'state', e.state, 'provenance', e.provenance,
    'role', p.role, 'ordinal', p.ordinal, 'selection', to_jsonb(s),
    'post', to_jsonb(t), 'publication', to_jsonb(pub), 'approval', to_jsonb(ap),
    'category', to_jsonb(c), 'category_config', to_jsonb(cc),
    'ancestry_ok', c.id IS NOT NULL AND NOT EXISTS (
       SELECT 1 FROM classifier_category a
       LEFT JOIN classifier_sitecategoryconfiguration ac
         ON ac.category_id=a.id AND ac.site_id=%(site)s AND ac.content_locale=%(locale)s
       WHERE a.tree_id=c.tree_id AND a.lft<=c.lft AND a.rght>=c.rght
       AND (NOT a.is_active OR ac.id IS NULL OR NOT ac.visible
            OR ac.canonical_path !~ '^/($|[^/])' OR ac.canonical_path ~ '[?#\\\\]')
    )
 ) ORDER BY p.role,p.ordinal)
 FROM catalog_relationparticipant p JOIN catalog_catalogentity e ON e.id=p.entity_id
 LEFT JOIN catalog_entitypresentationselection s ON s.entity_id=e.id AND s.site_id=%(site)s
    AND s.content_locale=%(locale)s AND s.approved
 LEFT JOIN post t ON t.id=s.post_id
 LEFT JOIN posts_sitepostpublication pub ON pub.post_id=t.id AND pub.site_id=%(site)s
    AND pub.content_locale=%(locale)s
 LEFT JOIN posts_postpublicationapproval ap ON ap.id=pub.approval_id
 LEFT JOIN classifier_category c ON c.id=COALESCE(t.rubric_id,s.category_id)
 LEFT JOIN classifier_sitecategoryconfiguration cc ON cc.category_id=c.id
    AND cc.site_id=%(site)s AND cc.content_locale=%(locale)s
 WHERE p.revision_id=v.id),
 'allow_legacy_und', policy.allow_legacy_und
)
FROM catalog_relationrelease l
JOIN catalog_relationrecord r ON r.id=l.record_id
JOIN catalog_relationrevision v ON v.id=l.approved_revision_id AND v.record_id=r.id
JOIN classifier_sitecontentpolicy policy ON policy.site_id=l.site_id AND policy.active
LEFT JOIN catalog_plantprotectionapplicationdetails d ON d.revision_id=v.id
LEFT JOIN catalog_applicationcountrypolicy cp ON cp.country=v.country
LEFT JOIN catalog_applicationmethod m ON m.code=d.method_id
LEFT JOIN catalog_relationwithdrawal w ON w.record_id=r.id AND w.resulting_epoch=v.created_epoch
WHERE l.site_id=%(site)s AND l.enabled AND NOT r.archived AND NOT r.withdrawn
 AND r.superseded_by_id IS NULL AND r.relation_type_id=%(type)s
 AND jsonb_typeof(policy.content_locales)='array'
 AND (v.country='' OR v.country=%(country)s)
 AND v.sealed AND v.state='approved' AND v.created_epoch=r.eligibility_epoch
 AND v.approval_epoch=r.eligibility_epoch AND policy.content_locales ? %(locale)s
 AND NOT EXISTS (SELECT 1 FROM catalog_sourcewithdrawalgate g
   WHERE g.relation_type_id=r.relation_type_id AND g.country=v.country
   AND g.source_version_digest=v.source_version_digest)
 AND NOT EXISTS (SELECT 1 FROM catalog_relationscopegate g
   WHERE g.relation_type_id=r.relation_type_id AND g.country=v.country AND g.quarantined)
 AND EXISTS (SELECT 1 FROM catalog_relationparticipant cx
   WHERE cx.revision_id=v.id AND cx.role=%(context_role)s AND cx.entity_id=%(page)s::uuid)
"""


def _data_query(context, config, filters):
    params = dict(
        site=context.site_id,
        locale=context.content_locale,
        type=config["type"],
        context_role=config["context_role"],
        page=context.page_entity,
        country=context.country,
    )
    sql = _SQL
    if config["type"] == "plant_protection_application":
        sql += " AND v.country=%(country)s"
        params["country"] = context.country
    for index, (key, value) in enumerate(filters.items()):
        if key == "method":
            sql += " AND d.method_id=%(method)s"
            params["method"] = value
        elif key != "kind":
            sql += f" AND EXISTS (SELECT 1 FROM catalog_relationparticipant f WHERE f.revision_id=v.id AND f.role=%(role{index})s AND f.entity_id=ANY(%(ids{index})s::uuid[]))"
            params[f"role{index}"] = key
            params[f"ids{index}"] = value
    return sql, params


def _card(p, context, now, allow_und):
    s, c, pub, ap, post = (p[key] for key in ("selection", "category", "publication", "approval", "post"))
    if p["state"] != "active" or not s or not s["approved"] or not c or not p["ancestry_ok"]:
        return None
    if post:
        if (
            post["entity_id"] != p["id"]
            or not post["status"]
            or _dt(post["publish_date"]) > now
            or not pub
            or not pub["enabled"]
            or _dt(pub["publish_at"]) > now
            or pub["category_id"] != post["rubric_id"]
            or not ap
            or ap["post_id"] != post["id"]
            or ap["content_locale"] != context.content_locale
            or _dt(ap["reviewed_at"]) > now
            or not ap["provenance"]
            or ap["content_digest"] != material_digest(SimpleNamespace(**post))
            or not _canonical(pub["canonical_path"])
            or pub["canonical_path"] != post["absolute_url"]
        ):
            return None
        if context.content_locale == "und":
            if (
                not allow_und
                or not ap["legacy_published"]
                or ap["language_verified"]
                or ap["legacy_site_id"] != context.site_id
            ):
                return None
        elif not ap["language_verified"]:
            return None
        title, url = post["title"], pub["canonical_path"]
    elif s["category_id"] and p["kind"] == "crop" and c["entity_id"] == p["id"]:
        cfg = p["category_config"]
        if not cfg or not cfg["visible"] or not _canonical(cfg["canonical_path"]):
            return None
        title, url = c["value"], cfg["canonical_path"]
    else:
        return None
    return dict(id=p["id"], kind=p["kind"], title=title, url=url)


def _dt(value):
    from datetime import datetime

    return datetime.fromisoformat(value)


def _application_ok(row, now):
    d, policy = row["application"], row["country_policy"]
    if not d or not policy or not policy["active"] or not row["method_active"]:
        return False
    try:
        today = now.astimezone(ZoneInfo(policy["timezone_name"])).date().isoformat()
    except ValueError, ZoneInfoNotFoundError:
        return False
    prep = next((p for p in row["participants"] if p["role"] == "preparation"), None)
    return bool(
        prep
        and isinstance(prep["provenance"], dict)
        and prep["provenance"].get("formulation_identity") == d["formulation_identity"]
        and d["formulation_verified"] is True
        and d["formulation_provenance"]
        and d["regulatory_decision"] == "confirmed"
        and d["regulatory_provenance"]
        and d["checked_at"]
        and _dt(d["checked_at"]) <= now
        and (not row["withdrawn_at"] or _dt(d["checked_at"]) >= _dt(row["withdrawn_at"]))
        and d["valid_from"]
        and d["valid_until"]
        and d["valid_from"] <= today <= d["valid_until"]
    )


def select_related_catalog(context, block_config, *, filters=None, cursor=None):
    """Return eligible cards/details/counts/facets; no writes or cache access.

    Preview uses the same public policy and never reveals drafts. A
    separate private history API owns draft inspection. URLs are scoped
    canonical anchors.
    """
    if not isinstance(context, CatalogContext) or context._verified is not _CONTEXT:
        raise ValidationError("A resolved catalog context is required.")
    if cursor is not None and not isinstance(cursor, str):
        raise ValidationError("Invalid or foreign selector cursor.")
    filters = _spec(block_config, {} if filters is None else filters)
    binding = hashlib.sha256(
        json.dumps(
            {
                "site": context.site_id,
                "locale": context.content_locale,
                "country": context.country,
                "page": context.page_entity,
                "config": block_config,
                "filters": filters,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    after = None
    if cursor is not None:
        try:
            token = signing.loads(cursor, salt=_SALT)
            if token["binding"] != binding or not isinstance(token["after"], list) or len(token["after"]) != 2:
                raise ValueError
            after = tuple(token["after"])
            if not all(isinstance(v, str) for v in after):
                raise ValueError
        except (signing.BadSignature, ValueError, KeyError, TypeError) as exc:
            raise ValidationError("Invalid or foreign selector cursor.") from exc
    sql, params = _data_query(context, block_config, filters)
    with connection.cursor() as db:
        db.execute(sql, params)
        rows = [json.loads(row[0]) if isinstance(row[0], str) else row[0] for row in db.fetchall()]
    now = timezone.now()
    cards, facet_sets = {}, {}
    for row in rows:
        participants = row["participants"] or []
        resolved = {p["id"]: _card(p, context, now, row["allow_legacy_und"]) for p in participants}
        if not participants or not all(resolved.values()):
            continue
        if row["type"] == "plant_protection_application" and not _application_ok(row, now):
            continue
        results = [
            p
            for p in participants
            if p["role"] == block_config["result_role"]
            and p["id"] != context.page_entity
            and (not filters.get("kind") or p["kind"] == filters["kind"])
        ]
        if not results:
            continue
        for p in participants:
            key = (p["id"], resolved[p["id"]]["title"])
            facet_sets.setdefault(p["role"], set()).add(key)
        if row["application"]:
            facet_sets.setdefault("method", set()).add(
                (row["application"]["method_id"], row["application"]["method_id"])
            )
        for p in results:
            card = cards.setdefault(p["id"], {**resolved[p["id"]], "details": []})
            detail = dict(
                record_id=row["record_id"],
                revision_id=row["revision_id"],
                type=row["type"],
                participants={
                    role: sorted(q["id"] for q in participants if q["role"] == role)
                    for role in {q["role"] for q in participants}
                },
            )
            if row["application"]:
                d = row["application"]
                detail.update(
                    {
                        key: d[key]
                        for key in (
                            "method_id",
                            "target_kind",
                            "target_text",
                            "valid_from",
                            "valid_until",
                            "registration_authority",
                            "registration_record_key",
                            "source_reference",
                            "source_document",
                            "source_version",
                        )
                    }
                )
                detail["country"] = row["country"]
            card["details"].append(detail)
    ordered = sorted(cards.values(), key=lambda c: (c["title"], c["id"]))
    for card in ordered:
        card["details"].sort(key=lambda d: (d["record_id"], d["revision_id"]))
    remaining = [c for c in ordered if after is None or (c["title"], c["id"]) > after]
    page = remaining[: block_config["page_size"]]
    next_cursor = None
    if len(remaining) > len(page):
        last = page[-1]
        next_cursor = signing.dumps({"binding": binding, "after": [last["title"], last["id"]]}, salt=_SALT)
    return dict(
        version=1,
        results=page,
        count=len(ordered),
        next_cursor=next_cursor,
        facets={
            role: [dict(id=id_, label=label) for id_, label in sorted(values)]
            for role, values in sorted(facet_sets.items())
        },
    )
