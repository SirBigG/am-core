# Shared catalog selection

`core.catalog.selection.select_related_catalog(context, block_config, filters=..., cursor=...)` is the public-policy read service for page renderers, public API, public Admin preview and catalog-to-market navigation. It changes no existing article URL, Post/Category ownership, Product.post, registry or Guide placement. This service adds no HTTP route, block configuration model or page widget. Those integrations belong to AGRO-80/81 and the owning API/market adapters. A market consumer must still apply its own site-scoped offer eligibility; a relation is not a seller offer or regulatory assertion about a product.

## Context and bounded configuration

Trusted routing supplies an explicit persisted Django Site, verified content language, market country and page CatalogEntity UUID to `resolve_catalog_context`. Do not construct context from unvalidated Host, UI locale or caller-selected country. It repeats live site/content policy in the data statement; absent/inactive/mismatched membership yields an empty selection. Unknown/malformed context fails validation. Current time comes from the server on every selection, with country-calendar application dates; a caller cannot request historical eligibility.

```python
context = resolve_catalog_context(
    site=resolved_site, content_locale="uk", country="UA", page_entity=crop_uuid,
)
config = {
    "version": 1,
    "type": "plant_protection_application",
    "context_role": "crop",
    "result_role": "preparation",
    "filters": ["target", "method", "kind"],
    "sort": "canonical_title_uuid",
    "page_size": 12,
}
page = select_related_catalog(context, config, filters={"target": [target_uuid]})
```

The config is the query projection of a future saved block config. An owning adapter must validate its own slots/presentation/enablement and pass only these query fields. Unknown keys, type, role, sort or request filters raise Django ValidationError. Supported reviewed adapters are related_to, cultivar_of and plant_protection_application. Other domain schemas fail closed until their public eligibility adapter exists. Role names must exist in every installed version of that type. Swapping context_role/result_role gives reverse traversal; related_to uses member for both and excludes the current page entity.

A configured role filter accepts 1–50 explicit UUIDs, with at most 50 selected IDs across filters. IDs within one role are alternatives; different roles intersect on the same released revision. `method` is available only for applications; unknown method yields no matches. `kind` filters result entity kind. The relation type is fixed by config. Country is fixed by resolved context, not an overridable request filter. Page size is 1–20. These bounds do not authorize a query language, SQL, Python, external URLs or permission callbacks.

## Eligibility and result contract

The candidate query starts from one enabled site release and its selected sealed, approved revision. It applies every role/participant/method predicate to that revision ID. Drafts never replace live details. All records must be active, unwithdrawn, unsuperseded and at the current created/approval eligibility epoch. Blocked source versions and unresolved source scope quarantine are excluded synchronously.

One PostgreSQL statement returns the release and all presentation/material/ancestry/domain evidence from one MVCC snapshot. Every participant must have an active identity, approved explicit site/content-language selection and available publication or crop category configuration. All ancestors require active categories and visible canonical configuration. Post approval must match the full current material digest and language evidence; future dates, unknown language and foreign memberships fail closed. Legacy und requires explicit publication on its original site and site policy opt-in. SEO-only changes preserve eligibility. Changed current body/source hides the relation until reviewed material qualifies again; this does not implement the broader AGRO-4 pending/live text renderer.

Applications additionally require active method/country policy and a verified timezone, matching preparation formulation identity, complete confirmed evidence, current checked-at and inclusive country-local validity dates. Reinstatement check time must follow the withdrawal. No ingredient or title-based matching is performed.

Only after every gate passes does the service build result cards. Cards deduplicate by entity UUID; each eligible application remains a separate detail with its method, source reference/document/version, registration, validity and exact participants. No private draft payload, evidence object, actor or audit history is serialized. Scoped canonical title and URL come from the approved presentation. A generic relation detail exposes only relation/revision/type and participant IDs.

The response contains `version`, `results`, deduplicated `count`, `next_cursor` and facets from the same eligible filtered set. Hidden rows supply neither counts nor facet labels. Details and facets are deterministically ordered. Cards sort by exact canonical title Unicode order, then UUID. The signed keyset cursor binds site, content language, country, page entity, config and normalized filters. A foreign/tampered cursor raises ValidationError; a valid cursor reevaluates current visibility, never certifies old eligibility. Counts always refer to the current full filtered set, not the remaining cursor suffix. Under unchanged data pages are stable; concurrent title/publication changes naturally change the live set.

## Query budget, indexes and cache

The normal call uses exactly **two SQL statements**: immutable type-role validation and one snapshot data query. It performs no ORM query inside row/participant/card loops. All gates precede dedup/count/facets/keyset pagination; candidate rows are never truncated before eligibility. Processing reads the full context-scoped match set and hashes current material in memory, so cost grows with matching revisions/material bytes. This is a measured first delivery, not a production volume capacity claim.

Existing indexes cover site/enabled/record/approved_revision (`catalog_release_lookup_idx`), entity/role/revision (`catalog_entity_role_idx`), revision/role/entity and revision/role/ordinal unique keys, country/source/record (`catalog_revision_source_idx`), source/scope unique keys, presentation/site/entity/locale and publication/category memberships. The ancestry query uses the MPTT tree index and scoped category configurations. No new migration is justified by the initial EXPLAIN baseline.

Maker PostgreSQL15.1 baseline with 25 typed released applications: two SQL statements for every 5-card page, dedup count25 and no omitted/duplicate keys. EXPLAIN ANALYZE BUFFERS returned25 candidate rows in approximately6.9ms on the disposable local fixture; the full JSON plan is retained in the task run's maker log. This timing is descriptive, hardware/fixture-specific. Required automated budget is at most two SQL statements per normal call and max20 cards/page; no N+1. Full current catalog/API/Admin/parser regressions accompany the focused selector tests. Independent review reports its own commands and results separately.

Independent acceptance additionally populated 10,000 guarded approved application revisions/releases across 20 preparation anchors. EXPLAIN returned all10,000 rows in approximately2.48s using indexed release and participant paths. Cold and repeated reads at page sizes1/20 used two SQL statements; three blocks used six, within the ADR budgets of8/16. Full deferred fixture validation took about25.6minutes and is recorded separately from selector read time. The complete plan and commands are retained in the AGRO-78 independent report. These are synthetic local measurements, not a production latency guarantee.

Both candidate and final-result caching are **disabled**. Fresh database membership, material, category ancestry, source gates and country time are evaluated for every request, including after bulk SQL updates, expiry and a stopped worker. The service never reads or writes Django cache. Existing cached Crop/Guide contexts must call it after retrieving their context rather than store its output. Durable generation/outbox remains AGRO-10's prerequisite for a future reviewed candidate-cache optimization. No parallel invalidation system is introduced here.

## Remaining integration

AGRO-85 consumes this shared service for application selection and false-intersection/visibility proof. AGRO-80 owns saved block configuration and manual replacement. AGRO-81 owns HTML/public API placement, filters/reset/mobile/keyboard and canonical/noindex query variants. Public UI, complete feature recovery and real agronomic source acceptance are not established by a selector test. No production feature was enabled, no mappings/grants seeded and no deployment performed.
