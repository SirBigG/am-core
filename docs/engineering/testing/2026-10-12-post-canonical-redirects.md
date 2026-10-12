# Post canonical redirects

PostDetail now resolves the existing post once and compares the request path
with its current get_absolute_url() before building context or rendering.
Different category or slug paths return HTTP 301 to the current path; canonical
paths render normally. GET and HEAD behave identically. Query parameters are
discarded on redirects and do not trigger redirects on canonical paths.
The existing object lookup and visibility policy are unchanged.

Five database-free Django tests passed in the host project uv environment:
`core.posts.tests.test_canonical_redirects`, using `settings.test_settings` and
environment values loaded without printing credentials from `../am.env`.
They cover old categories, old slugs, canonical rendering, HEAD, and missing IDs.
Object lookup and rendering are mocked; these tests do not prove database
persistence, full template rendering, proxy behavior, or production deployment.
Flake8 passed for the changed view and test file. Existing Django warnings concern
CKEditor and the nonunique email username; existing naive-datetime warnings also
appear during application startup. Compose has no running services.

Production still returned HTTP 200 for an alternative category path on
2026-10-12. Before moving content, deploy this view and prove that an alternative
path returns 301 to the current canonical path. Only then change category via
the authenticated Content API, preserving IDs, slugs, body and metadata.
Verify each old path returns 301 directly to the new path, which returns 200 and
has the new canonical. No production write or deployment has occurred here.

## Deployment handoff

This change requires deployment of the main `am-core` application and reload or
restart of its application workers. It adds no migrations, dependencies, static
assets, environment variables, or Nginx configuration. Use the existing deployment
process for the core service; the forum is unaffected.

Before moving any articles, check this deliberately noncanonical URL:

```bash
curl -sS -I 'https://agromega.in.ua/kartoplya/hvoroby-kartopli/parsha-zvychajna-3926.html'
```

Expected: HTTP 301 with `Location` pointing to the current article path:
`/koreneplidni/koreneplidni-user/parsha-zvychajna-3926.html`.
That source URL must still return HTTP 200. An HTTP 200 on the deliberately
noncanonical path means the redirect fix is not active; do not move content yet.
GET must also return 301 without following redirects; the retained migration
script verifies this before any PATCH. No actual article URL changes in this
deployment; URL changes happen only during the separate Content API operation.

Create the two additional active subcategories as children of `Картопля`:
`Шкідники картоплі` and `Фізіологічні порушення`. Their numeric IDs and exact
slugs will be read from the production category tree before classification.
After deployment and category creation, refresh the inventory and dry-run;
previous snapshots must not be used blindly after editorial changes.
