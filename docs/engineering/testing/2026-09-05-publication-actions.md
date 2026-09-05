# Publication market link and compact actions

Implemented and verified locally on 2026-09-05. No deployment or migrations.

## Identity and visibility

`Post` owns the market catalog identity. `Product.post` is the explicit relation;
`Variety.publication` links a separate registry record to that post. For example,
local Mikado is Post 3948 but registry Variety 2250. Market URLs use
`reverse("market:variety", args=[post.pk])`, and labels use `Post.title`, not
`page_h1` or SEO metadata. MarketPage fields configure market landing pages,
not per-publication calls to action; they were not duplicated.

`publication_market_context()` uses `market_offers().filter(post_id=...).exists()`:
the identical public eligibility query used by the destination. This includes
active product/company, published post, active and matching category, positive
price (or positive minimum without a fixed price), and a fresh observation.
It makes one existence query when eligible offers exist, at most two otherwise;
the rendering component makes no queries. No seller requests or new cache exist.
Freshness expiry and parser/admin changes therefore apply on the next render.

There is no general post-type discriminator. Registry-linked posts and posts
with an explicit product link in the post's category replace the old list even
when all offers are stale or inactive. Other posts retain `products_for_post`.
The category check only validates an existing Product.post relationship; category
membership or title words never establish a link. The component renders nothing
without an eligible offer, and never falls back to the old list on these identities.
Company pages and the legacy inclusion tag/template were not modified.

## Sharing, voting and analytics

The single action row follows content, attributes, registry, sources and the
optional market link. Sharing uses the rendered canonical link and post title.
Unavailable/failed Web Share offers a copy button; clipboard failure exposes a
selectable URL. AbortError is silent and copied confirmation uses a live region.
The existing Facebook mechanism remains a keyboard-accessible no-JavaScript fallback.

UsefulStatistic records are persisted by PostUsefulView and are available in
UsefulStatisticAdmin and the permission-gated admin dashboard. Voting is retained.
The existing anonymous endpoint, payload, CSRF header and server deduplication
remain unchanged. The UI prevents pending/successful repeat submissions, displays
the selected choice only after success, and enables retry on errors or timeout.
No new rating model, public counts or structured ratings were added.

**Existing limitation:** the client sends the constant `fingerprint` value, and
the API deduplicates the complete payload with an exists/create check. Identical
anonymous choices across readers collapse together, and this is not an atomic
per-person voting system. Admin totals must not be interpreted as unique voters.
This UI task does not redesign identity, concurrency or anonymous access policy.

The existing Google Analytics consent controller now exposes a gated event helper.
`agromarket_click` carries `post_id`, `entity_id` and `placement=after_content`.
It requires current consent and checks saved consent for revocation; failed storage
writes cannot re-enable tracking after rejection. No tracker is added, and default
link navigation is never cancelled or delayed for analytics.

## Verification

- 14 Django tests passed: `core.companies.test_market` and
  `api.v1.posts.tests.test_views.PostUsefulViewTests`, using settings.test_settings.
  New tests cover visibility changes, wrong/unlinked entities, inactive public
  state, staleness, escaping, canonical catalog labels, resolved URLs, bounded
  query count, preservation of legacy products and actual post-page placement.
- 6 Node tests passed: `node --test frontend/tests/publication-actions.test.cjs`.
  These exercise native share arguments/cancellation, copy failure/success,
  pending/repeated votes, HTTP/network/invalid-response errors and consent
  revocation when storage writes fail. They use controlled DOM/API doubles.
- Scoped pre-commit passed (formatting, Python checks, Bandit, Django template lint).
- Webpack production build and local collectstatic passed. Existing Sass import
  deprecation warnings remain. Django reports existing CKEditor, non-unique email
  and naive-datetime warnings. No unrelated dependency upgrades were attempted.
- Browser preview used the user-selected local Golden Delicious post 460 at
  1280x800 and 390x844. One market link and one action row were present; no old
  product list remained. Measured document width matched viewport width.
- The real link opened `/agromarket/variety/460/` in the same tab and displayed
  three existing offers. Keyboard focus is visible. Native sharing was invoked;
  Escape returned the share button to its enabled state without an error.
- A temporary fixture rendered the actual component with a 420-character unbroken
  name at 320px: no horizontal overflow. It contained no scripts; clicking its
  resolved link reached the existing local Golden Delicious market page.
- Local eligibility: apple Gala 455 and Golden Delicious 460 show the link;
  Mikado 3948 and potato Gala 3392 have no eligible offers and hide it.

Browser screenshots are local artifacts in `/tmp/agromega-publication-ui/`:
`golden-desktop.png`, `golden-mobile.png`, `long-name-mobile.png`.

Not verified: an actual external share delivery, clipboard fallbacks on every
browser/OS, real analytics delivery to Google, production deployment or a full
repository test suite. Vote writes/error responses and repeat handling were
verified in isolated tests, without adding feedback records to the local catalog.

## Data follow-up

The local Mikado record has Product 2779 (a herbicide) linked to it. It is not an
eligible current offer. The public [Mikado article](https://agromega.in.ua/kartoplya/kartoplia-sorty/mikado-3948.html)
also displayed herbicides in the old product block when inspected. These links
need separate admin matching review; no mapping or article data was edited here.
The new UI deliberately trusts the existing explicit relationship and shared
market eligibility, so it cannot independently repair a semantically wrong link.

## Changed files

- `core/companies/market.py`
- `core/companies/templates/companies/publication_market_link.html`
- `core/companies/test_market.py`
- `core/posts/views.py`
- `core/posts/templates/posts/detail.html`
- `core/posts/templates/posts/publication_actions.html`
- `frontend/src/js/detail.js`
- `frontend/src/scss/detail.scss`
- `frontend/tests/publication-actions.test.cjs`
- `core/posts/static/posts/j-detail.js`
- `core/posts/static/posts/detail.css`
- `templates/base.html`
- This verification note and `docs/business/domains/catalog-information/README.md`.

The detail template versions its two changed assets to prevent old cached JS from
running against the new DOM. Future deployment should include both compiled assets
and normal collectstatic. No database migration is required.
