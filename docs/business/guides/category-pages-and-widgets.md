# Managing category pages, Crop Hubs and Guide Hubs

Updated: 2026-10-17. Audience: content editors, administrators and agents.

Use this guide to assemble landing pages from existing catalogs and articles.
Configuration is stored in the database and managed in Django Admin or the
authenticated content API. Adding another crop does not require a category list
in application code.

## Choose the page type

| Page type | Use it for | How to select it |
| --- | --- | --- |
| Catalog | Browsing a category's existing articles or varieties and available filters | Category **Presentation mode = catalog**, with no active Category Hub |
| Guide Hub | An ordered reading path made from existing articles | Category **Presentation mode = guide hub**, with no active Category Hub |
| Crop Hub / Category Hub | A main crop landing page joining catalogs, practical guides and Agromarket observations | An active **Category hub** record attached to that category |

An active Category Hub takes precedence over the category's presentation mode.
There is no `crop_hub` value to choose in **Presentation mode**. Disabling the
Category Hub restores the underlying catalog or Guide Hub presentation.

Use the main crop category for a Crop Hub: for example, `/kartoplya/`, at the
same level as `/koreneplidni/`. A nested variety catalog or growing-guide
category is a source for that landing page. Standalone Guide Hub rendering
currently uses the existing two-segment category route, such as
`/kartoplya/vyroshchuvannia/`; use the Crop Hub for the main crop landing.

These are predefined page blocks, rather than a general drag-and-drop page
builder. Editors control category references, labels, introductions, visibility,
and ordering within navigation and guides. The overall page layout and order of
its major blocks are defined by the application.

## Understand the building blocks

| Admin object | What it owns | Example |
| --- | --- | --- |
| Category | Taxonomy identity, category URL, image and related metadata | Картопля |
| Category hub | Landing-page activation, short introduction, guide source and optional site/language restriction | Main potato landing |
| Hub section | A reference to an existing category, with a role and optional display label/description | Сорти картоплі → existing variety catalog |
| Guide section | A reading step with a title, optional description, order and visibility | Підготовка до посадки |
| Guide placement | An existing article referenced by a guide step, with its own order | Soil-preparation article in that step |

A Hub section links to a category and can supply a knowledge-count card. A
Guide section groups individual article links. They serve different purposes.
Adding a placement does not change the article's publisher, owning category,
body, publication status, slug or canonical URL.

Sources can come from another taxonomy branch. This lets a crop landing use
older catalogs without moving articles, copying categories or changing their
existing URLs. Local and production taxonomies can differ: discover the actual
records in each environment.

## Create or update a Crop Hub in Admin

1. Open **Classifier → Categorys** (`/admin/classifier/category/`) and identify
   the main crop category. Check its saved public URL and active ancestors.
   Reuse that category when it already exists. Creating or moving taxonomy
   categories is a separate editorial decision.
2. Open **Classifier → Category hubs** (`/admin/classifier/categoryhub/`) and
   search for its existing configuration before adding another. Only one hub
   can belong to a category. Alternatively, use the **Category hub** inline on
   the category form, then follow its change link to configure Hub sections.
3. Select **Category**, write a concise **Short introduction**, and leave a new
   hub inactive while preparing it. An introduction should explain what the
   reader can find, without reproducing a full article.
4. Add **Hub sections**. Select each existing target category, choose its role,
   and set an optional **Label override**, description, order and active state.
   Use positions such as 10, 20 and 30 to leave room for later insertions.
5. Select **Guide category** to reuse an existing guide collection. Leave it
   blank to use Guide sections owned directly by the landing category. It
   selects one collection; it does not merge every guide below the category.
   The source can supply placements even when its own presentation is catalog.
6. Leave **Site** and **Locale** blank for the default behavior. Set them only
   when intentionally restricting where the hub appears. Locale must be an
   enabled application language. These fields do not translate articles or
   establish separate content ownership for different sites.
7. Save, check the references and activate the hub when ready for public review.
   Open the category's saved public URL and review its cards and destinations.

The existing **Preview Guide Hub** button previews the saved guide collection.
It does not preview the complete Crop Hub. There is currently no private,
inactive-Crop-Hub preview; use the local environment for full-page preparation
before activating production configuration.

### Hub section roles

| Role | Use it for | Effect |
| --- | --- | --- |
| `varieties` | The crop's actual variety catalog | Knowledge count, catalog action, featured varieties and marketplace identity scope |
| `diseases` | Existing disease catalog | Knowledge count and navigation card |
| `pests` | Existing pest catalog | Knowledge count and navigation card |
| `growing` | Existing growing/care category | Knowledge count, primary action, navigation and additional-content browse destination |
| `additional` | Another relevant category | Extra knowledge count and navigation card |

Each primary role can appear once. Multiple `additional` rows are allowed if
they reference different categories. A category can appear only once in a hub.
The target cannot be the landing category itself or one of its ancestors.
Optional missing sections are omitted; do not create empty categories simply
to fill the layout.

Choose a narrowly relevant variety catalog. That reference and its eligible
descendants define the crop's marketplace scope. A broad parent containing
carrots, potato diseases or agricultural chemicals is unsuitable as the potato
variety reference.

## Configure the growing sequence and standalone Guide Hubs

1. Open the category that will own the guide collection. This may be the main
   crop category or the separate source selected in **Guide category**.
2. Add rows in **Guide sections**, with titles, optional descriptions, order
   and active state. Save the category.
3. Follow each saved section's change link, or open **Posts → Guide sections**
   (`/admin/posts/guidesection/`). Add existing articles through the article
   placement inline. Set the order of each placement and save.
4. For a standalone guide page, set its category's **Presentation mode** to
   **guide hub**. If it has an active Category Hub, disable that configuration
   first to expose the standalone guide presentation.
5. Use **Preview Guide Hub** on a saved category or section form. It shows saved,
   publicly eligible material only. Unsaved changes and draft content are not
   included. Missing preview permissions or out-of-scope articles can cause 403.

A suggested crop sequence is: soil and planting-material preparation; planting;
care; nutrition and irrigation; protection; harvesting and storage. These are
editorial suggestions, not automatically created sections. Link only articles
that exist and actually answer the step's question.

Sections and placements sort by ascending `sort_order`, then record ID when
positions tie. The same article may appear in different sections, but cannot
be added twice to the same section. A standalone Guide Hub displays repeated
placements in their sections while counting unique articles. The Crop Hub
sequence displays each eligible article only in its first placement.

Empty or inactive sections are omitted. A standalone Guide Hub displays section
descriptions; the Crop Hub's embedded sequence currently displays section titles
and article links, without those descriptions. A missing saved article URL is
shown as an unlinked title in the standalone guide and omitted from the Crop Hub.

## What the Crop Hub widgets show

| Block | Source and behavior | Editor control |
| --- | --- | --- |
| Hero | Category name or metadata H1, breadcrumbs, optional existing image and short introduction | Category metadata/image; hub introduction |
| Main actions | Configured variety/growing destinations, guide anchor when populated, and scoped market link | Source references and available guide content |
| Knowledge metrics | Unique eligible articles in each configured category subtree | Targets and labels; numbers are calculated |
| Knowledge navigation | Links to the configured public categories | Role, label, description, order and active state |
| Agromarket metrics | Eligible seller/cultivar observations, distinct sellers, varieties with offers, and latest eligible observation date | Variety-category reference; source data quality |
| Market groups | Currently the catalog-variety offer destination | No seed/food/fertilizer group inference |
| Price summary | Currently an informative unavailable state | No manual price or automatic median is enabled |
| Growing sequence | Ordered Guide sections and article placements from the selected source | Guide curation |
| Featured varieties | Up to six eligible catalog articles ordered by title and ID, excluding articles already shown in the guide | Catalog membership; no popularity ranking or dedicated featured selector |
| Additional articles | Up to six recent eligible articles from the landing subtree, excluding configured source subtrees and already displayed articles | Article/category content; no separate manual widget list |

When guide placements exist without a configured `growing` section, a practical
materials metric links to the embedded sequence. When `growing` is configured,
its metric counts that category's article subtree; it need not equal the number
of curated guide placements.

Do not type observed counts into labels. A title such as “360 varieties” becomes
stale; use “Сорти картоплі” and let the metric supply the count.

## Visibility, metadata and refresh behavior

Crop Hub articles require enabled publication status, a non-future publication
date, a saved URL, and active owning-category ancestry. Source categories and
the landing category must also have active ancestry.

Standalone Guide Hub eligibility currently checks article status and active
ancestry, without the Crop Hub's additional future-date filter. Use publication
status to keep a preparation article out of a standalone guide; a future date
alone is not a reliable hiding mechanism there. Hidden content being absent
from discovery does not establish a new access restriction on its article URL.

The Crop Hub uses the category metadata title/H1 where configured and the hub
introduction as its description. The standalone guide uses the existing category
metadata, including introductory text. Editing a hub reference or placement does
not create a new article URL. Reparenting categories or editing article identity
is a separate operation with possible URL consequences.

Admin/API configuration saves and ordinary Guide section/placement changes are
reflected on the next hub read through configuration versioning. Changes to
source articles or offers can take up to five minutes to appear in cached hub
metrics. Linked market listings evaluate current eligibility, so temporary
count differences are possible. Standalone Guide Hub collections are uncached.
Bulk database updates bypass save hooks; use Admin/API for ordinary curation.

## Read marketplace numbers correctly

The hub summarizes observed AgroMega listings, not all Ukrainian market activity
or a verified count of producers. Its market and seller links use the same
`hub=<category-slug>` scope. Scoped pages identify the crop and link back to its
landing. Category selectors, tabs, reset links and the empty-state seller link
retain that scope.

Eligible observations require active product/company records, a public linked
article in the configured variety subtree, matching product/article categories,
a positive price or eligible minimum price, an `auto` or `confirmed` match,
exact trimmed case-insensitive product/catalog names, and a fresh, non-future
price timestamp. The freshness window is the smaller of the hub and existing
product-price limits; the hub default is 30 days.

One seller/cultivar pair contributes one observation, using the latest eligible
record. Several package listings for one seller and cultivar do not count as
several hub offers. `review` matches and broad product-name mentions are excluded.
Do not change a match status merely to make a dashboard number larger.

The current schema has no verified package mass/unit or seed-versus-food product
classification. Price analytics therefore remain unavailable even when offers
exist. Configuration thresholds alone do not enable them. Seed, food, fertilizers
and crop-protection products must not be mixed to produce a crop price.

## Agent/API workflow

The same records can be managed through the content API. Use an existing
approved token for an active staff account with the required model permissions.
Credentials belong in approved secret storage, never in guides or tracked files.
Browser session cookies do not authenticate these endpoints.

| Operation | Endpoint |
| --- | --- |
| Discover category IDs | `GET /api/content/categories/tree/` |
| Find a category's existing hub | `GET /api/content/hubs/?category=<category-id>` |
| Create/read/update hub configuration | `/api/content/hubs/` and `/api/content/hubs/<id>/` |
| Manage category references | `/api/content/hub-sections/`, filtered by `?hub=<hub-id>` |
| Manage guide steps | `/api/content/guide-sections/`, filtered by `?category=<category-id>` |
| Manage article placements | `/api/content/guide-placements/`, filtered by `?section=<section-id>` |
| Read/change catalog or Guide Hub mode | `GET/PATCH /api/content/categories/<id>/presentation/` |

Recommended sequence:

1. Discover IDs and read existing configuration in the target environment.
2. Create a new hub inactive, then create its explicit category references.
3. Reuse an existing guide source or create sections and article placements.
4. Read back saved configuration and returned URLs. Activate only the intended
   hub, then review the public page and scoped destinations.
5. After an ambiguous POST outcome, query the records before retrying. Collections
   are paginated: follow `next` rather than assuming the first page is complete.

POST creates records; PATCH updates fields; DELETE removes configuration or
placements where authorized. Update a section's category reference when changing
its destination. API parent ownership is immutable: a hub's owning category,
a Hub section's hub, a Guide section's category and a placement's section cannot
be moved by PATCH. Create the replacement under the intended parent, read it
back, then remove the old reference only when intended and authorized.

Taxonomy creation/reparenting is outside these configuration endpoints. The API
does not create credentials, grant access or deploy pages to another environment.
Field contracts, permission names, pagination and request examples are in the
[hub management API reference](../../engineering/api/hub-management.md).

## Review, disable and recover

Before activating a page, check its main category level and canonical URL;
correct source references; mobile layout; article/section order; meaningful
labels; market/seller scope; visibility and empty states. Review with the actual
editor account as well as with a public visitor. Admin access alone does not
grant every configuration or article-visibility permission.

To undo a presentation change, disable **Category hub → Active**, or restore
**Category → Presentation mode = catalog** for a standalone guide. Keep the
curation records so they can be reused. Deactivating a Crop Hub also makes its
`?hub=...` market scope unavailable rather than silently broadening the results.

Removing a Hub section deletes a reference. Removing a Guide placement deletes
an article link. Deleting a Guide section also deletes its placements. Deleting
a Category Hub deletes its Hub sections. Those operations preserve referenced
articles and source categories; deleting an actual taxonomy category has broader
existing cascade behavior and is not a way to switch a page off.

Deleting a populated Category Hub requires both hub-delete and Hub-section-delete
permission in Admin and the API. Admin checks cover direct/bulk deletion,
category-form inlines, category/subtree deletion, and deletion of a referenced
category in another branch. Empty hubs do not require child-delete permission.
Denied inline cascades roll back the category edit. Prefer deactivation for a
routine presentation rollback so the curated configuration remains available.
See the [deletion-permission verification record](../../engineering/security/2026-10-17-hub-deletion-permissions.md).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Ordinary catalog appears instead of the Crop Hub | Hub active state, owning category, site/locale restrictions and saved URL |
| Crop Hub appears instead of a standalone Guide Hub | Disable its active Category Hub to expose `guide_hub` mode |
| A knowledge card is missing | Reference active state, target/ancestor visibility, recursive target, and saved category URL |
| Guide step or article is missing | Saved placements, section/status/ancestry, source selection, URL, future-date rule and Crop Hub deduplication |
| Count differs from the number of guide links | Category-subtree count versus curated placement count; duplicates; article eligibility; cache age |
| Article search/preview is denied | Staff/model permissions and global versus own-article visibility |
| Offers/sellers are zero despite raw products | Match quality, exact name, linked article/category, price, freshness and active state |
| Prices remain unavailable | Verified units and product purpose are absent; adding observations alone does not enable analytics |
| API returns 401/403 | Token authentication, active staff status and action-specific permission; guide article visibility |
| API returns 400 | Duplicate role/reference, invalid parent change, locale/order validation or conflicting write |
| `?hub=...` returns 404 | The hub must exist, be active, match the site/language and have public category ancestry |

## Related knowledge-base references

- [Hub management API](../../engineering/api/hub-management.md)
- [Crop Hub implementation and local inventory](../../engineering/crop-hubs/2026-10-17-category-hubs.md)
- [Guide Hub data and preview rules](../../engineering/guide-hub-foundation.md)
- [Guide Hub deployment and recovery](../../engineering/guide-hub-rollout.md)

Deployment is separate from editorial configuration. Apply the target release's
migrations before new-code workers serve requests and follow the existing static
build/collection process. Crop Hub configuration requires classifier migrations
0016/0017 in addition to the Guide Hub foundation; inspect the actual migration
plan in the target environment. Local hub records and content are not seeded by
these migrations and are not transferred by deploying application code.
