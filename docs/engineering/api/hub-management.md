# Hub and Guide Hub management API

Implemented 2026-10-17 under the existing `/api/content/` namespace. These endpoints manage the same configuration records as Django admin. They do not copy categories, move publications, change article bodies, regenerate article/category URLs, or provision agent credentials.

## Authentication and permissions

Use the existing `Authorization: Token <token>` mechanism. Session cookies are not accepted for these endpoints. Requests require an active staff account and the operation-specific Django model permission. GET/HEAD/OPTIONS explicitly require view permission, unlike DRF's default model-permission map. Responses, including errors, are private and non-cacheable.

| Resource | Permission model |
| --- | --- |
| Hubs | `classifier.categoryhub` |
| Hub sections | `classifier.categoryhubsection` |
| Guide sections | `posts.guidesection` |
| Guide placements | `posts.guidesectionarticle` |
| Category presentation | `classifier.category` |

For each model, grant only the necessary `view_`, `add_`, `change_`, and `delete_` codenames. For example, a hub reader needs `classifier.view_categoryhub`; changing it needs `classifier.change_categoryhub`. Category presentation changes need `classifier.change_category`. No new permissions or tokens were granted to existing accounts by this implementation.

Guide placement discovery and Post selectors also use the existing admin Post visibility policy: global `posts.view_post`/`posts.change_post`, or `posts.change_own_post` restricted to the account's own Posts. Hidden Post references return 404 on detail/update/delete, are absent from lists, and cannot be selected through forged create/update payloads. Draft articles remain manageable by authorized editors, but public pages still enforce publication status and active ancestry.

## Endpoints

The four collection/detail pairs support GET/POST on collections and GET/PUT/PATCH/DELETE on detail URLs. Collections use existing content pagination: 20 by default, `page_size` up to 100. IDs are integer primary keys of existing records. Filter values must be positive integer IDs.

| Collection | Detail | Optional list filter |
| --- | --- | --- |
| `/api/content/hubs/` | `/api/content/hubs/<id>/` | `?category=<category-id>` |
| `/api/content/hub-sections/` | `/api/content/hub-sections/<id>/` | `?hub=<hub-id>` |
| `/api/content/guide-sections/` | `/api/content/guide-sections/<id>/` | `?category=<category-id>` |
| `/api/content/guide-placements/` | `/api/content/guide-placements/<id>/` | `?section=<section-id>` |

`/api/content/categories/<category-id>/presentation/` supports GET and PATCH. It returns `id`, `slug`, `value`, saved `url`, and `presentation_mode`; only `presentation_mode` is writable (`catalog` or `guide_hub`). The update touches only that database column, preserving existing category images and saved URLs. An active CategoryHub continues to take presentation precedence; disable that hub when reviewing the ordinary Guide Hub presentation.

Existing `/api/content/categories/tree/`, post, country and attribute-schema endpoints retain their response contracts. Use the existing category tree to discover real category IDs and the new presentation endpoint for mode readback. OPTIONS describes fields where the account has view permission.

## Writable contracts

- **Hub:** `category` (required on create), `is_active` (defaults false), `description`, optional `guide_category`, `site`, and `locale`. `id`, `updated` and saved category `url` are read-only. One hub per category.
- **Hub section:** `hub`, `category`, `role`, `title`, `description`, `sort_order`, `is_active`. Roles: `varieties`, `diseases`, `pests`, `growing`, `additional`. Each primary role occurs at most once per hub; multiple `additional` rows may reference different categories. A category occurs at most once per hub. `url` is the referenced category's stored canonical URL.
- **Guide section:** `category`, `title`, `description`, `sort_order`, `is_active`.
- **Guide placement:** `section`, `post`, `sort_order`. Read-only `title` and `url` come from the existing Post. Each section/Post pair is unique.

Parent ownership is immutable on update: hub `category`, hub-section `hub`, guide-section `category`, and placement `section`. To relocate a reference, create it under the intended parent, read it back, then explicitly delete the old reference if authorized. Changing a placement never changes the Post itself.

Hub references may deliberately cross taxonomy branches. This supports existing catalogs and Guide Hub collections without reparenting content. A section cannot target its source hub or an ancestor whose catalog contains that hub. Referenced category ancestry must be public before it appears on the public page; inactive optional targets are safely omitted. Guide sources are direct collections and may be the hub itself or another existing category. Marketplace identity comes only from the explicit `varieties` reference and its public subtree, never from all categories below the landing page.

## Agent workflow

1. Discover categories and GET existing hub/section configuration before creating records. Do not retry an ambiguous POST blindly: resolve its outcome through readback using parent filters and reference IDs.
2. Create the hub inactive. Select the existing category, optional guide source, introduction and site/language restrictions.
3. Add explicit category sections; add or reuse GuideSection/GuideSectionArticle records for the growing sequence. Check canonical URLs returned by readback.
4. Read back configuration, then PATCH `is_active=true` on the hub. To expose a standalone Guide Hub, PATCH its category `presentation_mode=guide_hub`.
5. Review the server-rendered category URL and marketplace filter destinations. Invalid or incomplete price data still yields the existing informative empty state.

Example update (the environment variable is a placeholder for approved credential loading, never a tracked token):

```bash
curl --fail-with-body -X PATCH \
  -H "Authorization: Token ${AGROMEGA_CONTENT_TOKEN}" \
  -H 'Content-Type: application/json' \
  --data '{"description":"Оновлений короткий вступ"}' \
  http://localhost:8000/api/content/hubs/1/
```

Mutations are atomic. Configuration parents are locked before child edits; duplicate/conflicting relationships return 400 with no partial write. A populated hub cannot be deleted without `delete_categoryhubsection`. A populated GuideSection cannot be deleted without `delete_guidesectionarticle` and visibility of every referenced Post. Deleting a hub or guide section deletes only its configuration/placement rows, preserving categories and Posts.

Hub configuration changes immediately select a new aggregate cache snapshot. Guide section/placement saves and deletions update the affected hubs' database version timestamp, so those changes are reflected across worker caches on the next page read. Existing direct Guide Hub rendering remains uncached. Raw QuerySet bulk updates bypass save signals; ordinary source-content/offer expiry remains bounded by the existing maximum five-minute TTL.

## Local crop-level review configuration

The corrected landing category is `2467`, `/kartoplya/`, at level 1 under plant root 71, beside `/koreneplidni/`. Hub 1 belongs to it. Its `varieties` section references the older catalog 2327 at `/koreneplidni/sorty-kartopli/`, and `guide_category=2466` reuses the existing nested Guide Hub collection. The nested demo no longer owns a Crop Hub. The public landing shows 120 varieties, ten eligible guide articles and zero strict fresh market observations. No source article/category was copied or moved. Local IDs are examples only; discover IDs separately in every environment.

- Review: `http://localhost:8000/kartoplya/`
- Admin: `http://localhost:8000/admin/classifier/categoryhub/1/change/`
- Agent readback: `/api/content/hubs/?category=2467`, `/api/content/hub-sections/?hub=1`, `/api/content/guide-sections/?category=2466`.
- Market destinations: `/agromarket/?hub=kartoplya`, `/companies/?hub=kartoplya`.

Configure hubs on the main crop categories. Source catalogs and guide collections may live elsewhere in the legacy taxonomy; explicit category references connect them. Category creation/reparenting is still an admin operation, outside these configuration APIs. Source canonical URLs and article ownership remain independent of hub composition.

Final verification after correcting the landing level: **112/112 crop/admin/API/company tests pass**, including a main crop page backed by legacy sibling catalogs and guides, independent Guide Hub rendering, preservation of article URLs, strict market/seller scope and exclusion of unrelated root-crop records. Earlier broad verification ran 343 tests with two previously verified baseline failures (metadata alias redirect and sitemap group count). No production deployment, token provisioning or permission grant was performed.

Scoped marketplace/company pages display the culture and link back to its landing page. Their category selectors exclude unrelated crop categories; reset links and empty-state seller links retain the selected hub. Browser QA confirmed these flows and the corrected landing at mobile width 390 without horizontal overflow.
