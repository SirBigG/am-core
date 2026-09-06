# Decision: Separate international AgroMega application

- Date: 2026-09-06
- Status: Accepted (architecture direction; not deployed)
- Owners: AgroMega team

## Context

AgroMega will test Spain before expanding internationally. Existing Ukrainian content, URLs and search history must be preserved. The user chose a separate application and database instead of migrating am-core to a multilingual content schema. No new domain is required for the pilot.

## Decision

- Build a sibling Django + Wagtail application with server-rendered pages, independently owned dependencies, migrations, database credentials, static/media storage and deployment artifact. Wagtail integration details and supported versions must be validated in a local prototype before rollout.
- Initially route the explicit `/es/` namespace to the new application through Nginx. Existing routes remain owned by their current applications. Audit existing `/es/` and `/en/` responses before claiming either namespace; do not transfer `/en/` implicitly.
- Keep language separate from country/market. Spanish-first content needs no Ukrainian equivalent. Shared catalog entities and company/market data belong to Django domain models; editorial pages and revisions belong to Wagtail.
- The global product has no forum. Do not add discussion infrastructure, forum routes, forum navigation, forum SSO or a dependency on forum_instance. This is the agreed product scope, not a postponed pilot feature. The existing AgroMega forum remains owned by its current application.
- Transfer selected source content through an authenticated read API or a controlled export, with source identity and provenance. No cross-database foreign keys or direct access from the new application to the old database. Do not automatically overwrite translated editorial work.
- No legacy Post translation migration, old URL regeneration, domain purchase, public account migration, forum redesign or bulk registry import is part of the pilot.
- Moving the international section to a new domain is a later SEO migration with explicit URL mapping, redirects and retained old redirect endpoints. It is not merely a configuration toggle.

## Consequences

The old application avoids schema and content migration risk. The team takes on another deployment, backups, monitoring and content ownership boundary. Sharing a server or PostgreSQL cluster saves resources but does not provide failure isolation; database roles, connection limits and workload budgets must be configured.

Root robots and sitemap ownership, URL generation behind the proxy, asset paths and cookies require integration testing. Same-origin path separation is not a security boundary between applications.

## Existing routing discrepancy

On 2026-09-06, local `nginx/nginx.conf` redirects `/forum/` to `/community/`, while supplied workspace instructions require public forum URLs under `/forum/`. Production behavior was not inspected. Resolve the source-of-truth discrepancy before changing proxy configuration; do not alter forum routing as a side effect of this project.

## References

- [Wagtail internationalization](https://docs.wagtail.org/en/stable/advanced_topics/i18n.html)
- [Google: site moves with URL changes](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

References checked 2026-09-06. Implementation details and evidence will be recorded separately when verified.
