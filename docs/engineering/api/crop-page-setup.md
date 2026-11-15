# Crop-page setup API

Implemented 2026-11-15. These endpoints complete crop-page configuration alongside
the [hub APIs](hub-management.md), existing content/post/attribute APIs and
[company/parser APIs](../operations/distributed-product-parser-workers.md).
No admin session is needed for editorial setup. They do not provision credentials
or grant account permissions.

## Authentication and permissions

Use `Authorization: Token <token>` with an active staff account. Sessions are not
accepted. GET/HEAD/OPTIONS require the corresponding `view_` permission; POST
requires `add_`, PATCH requires `change_`, and photo DELETE requires `delete_`.

| Resource | Django permission model |
| --- | --- |
| Category taxonomy, nested SEO, category images | `classifier.category` |
| Hub layout and other hub configuration | `classifier.categoryhub` |
| Article photos | `posts.photo`, plus visibility/change access to the owning Post |
| Product-to-variety matching | `companies.product`, plus visibility of the selected Post |

Photo selectors respect the existing global/own-article admin policy. Maintaining
photos also requires `posts.change_post` or `posts.change_own_post` for the owning
article. Photo permissions alone cannot mutate an article's media. Product match
selectors use the same article visibility policy. Responses from the new category,
media and matching endpoints, including errors, are private and non-cacheable.
New writes record operator/target/changed fields in Django admin history in the
same database transaction. Existing hub permissions and behavior remain in place.

## Taxonomy and category SEO

| Endpoint | Methods |
| --- | --- |
| `/api/content/categories/` | GET, POST |
| `/api/content/categories/<id>/` | GET, PATCH |
| `/api/content/categories/<id>/images/` | GET, PATCH |

The management list includes inactive categories. It supports `parent=<id>`,
`parent=null` for structural roots, `is_active=true/false` and exact `slug`.
Pagination defaults to 20, with `page_size` up to 100; follow `next`.
The existing `/api/content/categories/tree/` active-tree contract is unchanged.
Category DELETE is unavailable; use `is_active=false` to remove a category from
ordinary discovery. Existing direct-URL visibility rules remain unchanged; this
flag does not create private preview pages.

Create a crop under an existing structural root, using discovered environment IDs:

```json
{
  "value": "Морква",
  "slug": "morkva",
  "parent": 71,
  "is_active": false,
  "presentation_mode": "catalog",
  "seo": {
    "title": "Морква: сорти та вирощування",
    "description": "Каталог сортів і практичні матеріали про моркву.",
    "h1": "Морква",
    "text": "<p>Вступний текст категорії.</p>"
  }
}
```

`value` and a unique `slug` are required; `parent` is an existing Category ID or
null for a structural root. `is_active` defaults to the model default, true;
explicitly create preparation categories inactive. Writable fields are `value`,
`slug`, `parent`, `is_active`, `presentation_mode` (`catalog`/`guide_hub`) and
nested `seo`. `id`, `url` and `level` are read-only. Unknown/read-only fields are
rejected. Slugs accept ASCII letters/digits, hyphens and underscores, max 250;
application prefixes, language prefixes and old paths belonging to another
category are reserved. Images are maintained through the separate endpoint.

PATCH only the intended fields. Nested SEO is merged with the current values:
`title`/`description` accept nonempty strings up to 255 characters, `h1` up to
255 (blank/null clears it), and `text` up to 200,000 (blank/null clears it).
When initially supplying only H1/text, title and description default to the
category name. `seo=null` detaches metadata and restores existing template
fallbacks. SEO records cannot be selected by ID. Changed metadata is copied
before attachment, isolating other domain objects that may share legacy metadata;
old metadata rows are retained. Repeating unchanged SEO does not create another
metadata row. Rich text is trusted editorial HTML, as in admin.

### Moves and URL preservation

PATCH `parent` to move a category or `slug` to rename its URL identity. The API
supports the application's public hierarchy: structural root (level 0), crop
(level 1), catalog/guide (level 2). It rejects cycles, moves exceeding this depth,
structural roots owning articles, and moves invalidating hub source references.
Nonstructural edits to pre-existing deeper legacy nodes remain possible.

Taxonomy writes serialize using a PostgreSQL table lock before reading or
validating tree state. MPTT updates, descendant category URLs, article URLs,
redirect records and audit history commit together. They do not change article
identity, body, publication state, prices or matching decisions. Label, SEO,
visibility and media edits preserve category/article URLs and existing images.

Previous canonical category paths redirect directly to the category's current
path with 301, preserving query parameters and supported language prefixes.
Renaming back removes the self-alias, avoiding loops. Inactive ancestry does not
produce an alias redirect. Old article URLs already resolve by ID and redirect
to the updated stored canonical URL. The API does not rewrite external links or
HTML links embedded in article bodies. These redirect guarantees apply to API
taxonomy edits; direct database updates/admin moves do not create these records.

Taxonomy/SEO/category-media changes version all crop-hub caches immediately;
underlying article and offer refresh rules retain their existing bounded TTL.

## Layout

`layout` is now readable/writable on `/api/content/hubs/` and
`/api/content/hubs/<id>/`: `standard` (default) or `sectioned`. For a page like the
potato landing, create the hub inactive with `layout="sectioned"`, then configure
its variety, growing, disease, pest and optional `protection` references, guide
steps, placements and optional `market_category`. Activate after preparation.

## Images and article photos

Category image PATCH accepts multipart `image` and/or `hero_image` uploads.
JSON PATCH `{ "hero_image": null }` clears only that reference; `{ "image": null }`
clears the thumbnail. An omitted field is unchanged. GET returns current URLs.
The hero keeps its original dimensions; the thumbnail is cropped to 300×200.

```bash
curl --fail-with-body -X PATCH \
  -H "Authorization: Token ${AGROMEGA_CONTENT_TOKEN}" \
  -F 'hero_image=@/absolute/path/crop-hero.jpg' \
  https://agromega.in.ua/api/content/categories/123/images/
```

Article photos use GET/POST `/api/content/photos/` and GET/PATCH/DELETE
`/api/content/photos/<id>/`. List filtering is `?post=<id>`, with the standard
content pagination. POST multipart fields are required `post` and `image`, plus
optional `description` (500 chars), `author` and `source` (150 each). PATCH may
replace the image or change attribution/description. The owning `post` is
immutable; DELETE removes a photo record. Null images are not valid for photos.
Photo images fit within 1000×800 without upscaling. Existing post reads still
return their `photos` projection; this is its separate maintenance API.

Uploads must decode as JPEG, PNG or WebP, at most 10 MiB, 24 megapixels and
12,000 pixels per side. The API re-encodes pixels to WebP with generated unique
storage names, strips embedded metadata and uses the configured Django storage.
Animated images contribute only their first frame. Remote URLs, SVGs and existing
storage paths are not accepted as uploads. No static build is needed for uploads.

Rollback attempts to remove newly written files; storage failures are logged for
operator cleanup. Storage is not transactional: process termination can leave an
orphan upload. Replaced/cleared/deleted references retain old files, following
existing Django behavior and preserving shared references/rollback options.
Storage garbage collection is a separate operation.

## Manual offer-to-variety matching

GET/PATCH `/api/content/products/<id>/match/` reads or confirms a decision.
PATCH `{ "post_id": 456 }` links to a visible, published, non-future article in
the product's exact category with active ancestry. PATCH `{ "post_id": null }`
confirms no match. Both set `match_status="confirmed"`; later imports preserve
the decision through the existing Product behavior. Price, observation timestamps
and history are untouched. Other product fields cannot be changed here.
Parser product reads also expose `post_id`, `match_status` and `match_reason`,
allowing an operator to discover offers needing review.

A confirmed match does not bypass existing market eligibility (price freshness,
publication/active state and, for strict hub scope, exact-name requirements).
This API does not add bulk algorithm reassessment or vocabulary management.

## Complete setup sequence and deployment

1. Discover existing roots, categories, articles and hub configuration. Reuse
   existing records; after an uncertain POST, query before retrying.
2. Create missing crop/source categories inactive, set SEO and upload images.
3. Create/update articles through `/api/content/posts/`, their attribute schema
   and values, and photos through the new photo API.
4. Create an inactive `sectioned` hub; add explicit knowledge references and
   curated guide steps/placements. Set `market_category` when desired.
5. Maintain sellers/parser configurations through `/api/parser/`, ingest offers,
   and confirm/correct catalog links through the matching endpoint as needed.
6. Read back every configuration, activate intended categories/hub, then review
   the public crop page and all linked catalog, guide and marketplace URLs.

Apply classifier migration **0020_category_url_redirect** before new-code web
workers serve requests: redirect middleware reads its table on category routes.
Deploy compatible application code and follow ordinary migration rollout ordering.
No category/content records, uploads, permissions or tokens are seeded. Reversal
drops redirect history; retain it when rolling back configuration. Existing page
templates and compiled static assets are unchanged by this API change.
