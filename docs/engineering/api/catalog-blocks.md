# Versioned hub catalog blocks

The existing hub-management API and **Classifier → Category hubs → Related catalog blocks** use one `BlockAccess` service. Configuration references an existing hub and its explicit crop CatalogEntity; no second hub, duplicate Post or title-based mapping is created. It is scoped to one site/content language. Nullable legacy hub.site/blank hub.locale do not make this configuration global: its own site and content locale are required. An explicit hub restriction must agree with the scope. Changing a hub's entity/site/locale later does not rebind the saved immutable owner.

## Editing and publication

A stable BlockConfiguration owns immutable numbered revisions, an active revision pointer, enablement/version and append-only actor/time audit. Saving appends a draft revision and keeps the current active pointer. Editors preview any saved revision against current public eligibility through the shared [selector](catalog-selection.md), including the exact manual placement manifest. A publisher explicitly activates the reviewed revision with its signed preview. The 15-minute preview binds actor/site/hub/language/country/base/revision and result/manifest digest; changed configuration, preview effects or rights require fresh review. `CATALOG_BLOCK_PREVIEW_MAX_AGE` controls the lifetime. Activation never approves or releases relation facts.

The configured site comes from the server's SITE_ID. Actions need active staff, explicit RelationSiteGrant, view_blockconfiguration plus hub/category view permissions and a participant grant for the hub crop identity. Save additionally needs add/change_blockconfiguration, classifier.change_categoryhub and site can_edit. Activation/disable need publish_blockconfiguration, classifier.change_categoryhub and site can_publish. No grants are seeded and a superuser without site/participant grants is denied. Fixed participant UUIDs need explicit current grants; historical configuration access also checks its participants. Manual replacement requires global post, Guide section and Guide placement view permissions. Existing generic hub-management permissions do not imply these new capabilities.

An active site policy and current eligible crop presentation are required for preview/activation. Private history and explicit disable remain available when public eligibility is inactive, provided the actor still has its editorial scope. Disabling retains revisions, active pointer, manual bindings and relation/source withdrawal state. Re-enabling requires a new preview and never restores withdrawn facts or disabled relation releases.

## Declarative rules

A revision holds one to three unique ordered slots. List order is display order. Supported pairs are crop.related_preparations (application crop→preparation), crop.related_problems (application crop→target), and crop.related_catalog (cultivar_of crop→cultivar or related_to member→member). Each block has exactly these fields:

```json
{
  "version": 1,
  "slot": "crop.related_preparations",
  "title": "Препарати за підтвердженими застосуваннями",
  "type": "plant_protection_application",
  "context_role": "crop",
  "result_role": "preparation",
  "filters": ["target", "method"],
  "conditions": {},
  "country_policy": "resolved_market",
  "sort": "canonical_title_uuid",
  "page_size": 12,
  "empty": "hide",
  "presentation": "catalog_cards",
  "manual_replacement": "none",
  "manual_ids": []
}
```

`filters` allowlists request filters supported by the reviewed selector/type. `conditions` fixes a subset of them, using explicit participant UUID lists or controlled method/kind values; runtime inputs cannot replace a fixed condition. Page size is 1–20; empty blocks are hidden; presentation is catalog_cards or catalog_list. All other keys, unsupported slots/type/roles/layouts, SQL/Python/templates/URL query languages and incompatible fields are rejected. Titles are literal escaped text. Another crop needs its own explicit entity/hub configuration, using the same rules without a Python crop ID/slug branch. Country comes from the resolved market context for each read; the operator supplies an explicit country when reviewing a configuration.

`manual_replacement: guide_placements` requires 1–50 explicit existing GuideSectionArticle IDs in `manual_ids`. They must belong to this hub's selected guide category (or its own category when no guide source is selected). A placement belongs to only one slot in a revision; total configuration limit is 50. The preview lists their current post, section and ordering. Activation does not delete, move, copy or rewrite them. Historical FK references protect them and their owning hub from deletion; the existing hub API returns a controlled409 for a protected delete. Editing an existing live hub's guide source requires reviewing a compatible replacement manifest before the next activation.

## Admin

Open a Category hub and choose **Related catalog blocks**. For an unrestricted hub, choose the content language explicitly; there is no UI-language fallback. Enter the ordered block array, save a draft, select a revision and country, and preview. Review the eligible cards/empty state, layout and manual manifest, then choose **Activate reviewed configuration**. The CSRF-protected form carries the current version and signed preview. Saving another draft preserves the active revision. **Disable automatic configuration** retains history and makes the explicit off-mode available to the later renderer.

## Existing hub-management API round-trip

The routes extend `/api/content/hubs/{hub_id}/`:

| Method/route | Body and condition |
| --- | --- |
| GET `catalog-blocks/?content_locale=uk` | Authorized scope/history/readback, configuration null before first creation |
| POST same | `{"blocks":[...]}`, If-None-Match:* for first creation; current If-Match for a revision |
| POST `catalog-blocks/preview/?content_locale=uk` | `{"revision_id":"...","country":"UA"}` |
| POST `catalog-blocks/activate/?content_locale=uk` | `{"preview":"signed token"}`, current If-Match |
| POST `catalog-blocks/disable/?content_locale=uk` | `{}`, current If-Match |

Readback contains version1, configuration UUID/hub/site/content_locale/owner UUID, enabled, active_revision_id, lock_version, quoted ETag, ordered revisions with their exact blocks/actors/timestamps and audit. Use the returned ETag, e.g. `"configuration-uuid:2"`; stale/missing preconditions return409/428. Unknown bodies/query parameters/actions return400. Authentication, no-store/noindex and the existing catalog error envelope apply. There is no raw PATCH/DELETE of active JSON or history. Repeating a stale write returns conflict; clients read back the active revision/version after an uncertain outcome. Concurrent writers serialize on the graph/site/hub/configuration locks and only one same-base draft commits.

## Reader contract and rollout boundary

`select_configured_blocks(resolved_context, hub_id, filters={slot: {...}}, cursors={slot: ...})` reads current enabled configuration, owner/site/language/hub binding and invokes the shared selector for every block. It adds no cache. One configuration query plus two per block gives 3 queries for one block or 7 for three, within the accepted8/16 budgets. No source facts or configuration are stored inside the old cached Crop Hub context.

The returned entries preserve slot ownership and explicit manual IDs even when selection is empty, with `visible=false`. AGRO-81 must omit the empty UI block while preserving automatic ownership of that slot, so an empty automatic result cannot silently fall back to an unverified manual list. Explicit configuration disable yields no automatic entries and permits the planned manual off-mode. Nonempty entries have visible=true and current canonical cards/counts/facets/cursors. The reader never mutates Guide/CategoryHubSection/market_category. AGRO-81 owns actual slot rendering, crop/problem/preparation/cultivar adapters, public API binding and manual→automatic page switching. No public page widget or endpoint is activated by these migrations.

Migrations0013/0014 are additive and seed no real mappings/configurations/grants. Database guards retain immutable scope/revisions/manual/audit, enforce bounds and same-configuration active pointer, and require exact manual binding manifests. Application disable/restore uses the enablement service, retaining all data; reversing populated schema is a separate destructive maintenance decision. Accepted selector10k EXPLAIN evidence may be reused when its source/query remains unchanged. Local tests use isolated PostgreSQL and synthetic data; production content, country/regulatory source acceptance and deployment remain separate gates.

The public page adapters and read API are documented in [Related catalog blocks on public pages](catalog-public-blocks.md).
