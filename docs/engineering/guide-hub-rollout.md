# Guide Hub rollout

Guide Hub is opt-in. Deploy schema and application code first; prepare real
collections separately in Admin while categories remain in `catalog` mode.
Do not copy the local database, fixtures, `content_refresh_runs/`, or the demo
category `kartoplia-guide-demo`. The Docker build excludes local content runs
and agent working files. Neither migration seeds content or grants roles.

## Release preflight

- Package the reviewed source, both new migrations and both admin/public
  templates in one versioned release. The current working copy is uncommitted;
  record the actual release revision before deployment.
- Verify the target host, database, production settings and current release.
  Take a restorable database backup and retain the previous application image.
  Use the existing production deployment process; the local Compose runserver
  is not a production deployment recipe.
- In the new release runtime with the target's production settings, run
  `python manage.py check`, `python manage.py check --deploy`,
  `python manage.py makemigrations --check --dry-run`, and
  `python manage.py migrate --plan`. Resolve unexpected operations before
  applying anything. Do not infer server migration state from local state.
- Expected new leaves are `classifier.0015_guide_hub_foundation` and
  `posts.0035_guide_hub_foundation`; their predecessors are classifier 0014 and
  posts 0034. The posts migration depends on classifier 0015. Inspect
  `python manage.py sqlmigrate classifier 0015` and
  `python manage.py sqlmigrate posts 0035` against the target runtime if needed.

## Schema and application deployment

Run `python manage.py migrate --noinput` once using the release runtime and
production settings, before serving the new application. Follow the established
static collection and application restart process. The Dockerfile's default
command does not itself run migrations; do not assume container startup applies
them. Avoid concurrent migration runners.

The classifier migration adds a non-null presentation field defaulting to
`catalog`. The posts migration creates two tables with foreign keys, ordering
fields and a unique `(section, post)` constraint. There is no article update,
URL regeneration or content backfill. Allow for schema locks on the category
table; actual timing depends on the target database and traffic.

After migration, check `python manage.py migrate --check` and
`python manage.py showmigrations classifier posts`. Django's post-migrate step
creates the eight standard GuideSection/GuideSectionArticle permissions.
Verify all eight exist before assigning approved editor groups.

## Explicit access assignments

Use existing user/group Admin. Do not grant superuser or global article-change
access merely to enable Guide Hub. Guide curation permissions are global, not
restricted to an article publisher or an individual guide.

| Role / operation | Required permissions |
| --- | --- |
| Read-only preview of a mixed-author guide | Active staff account; `classifier.view_category`, `posts.view_guidesection`, `posts.view_guidesectionarticle`, `posts.view_post` |
| Edit category presentation and section inline | `classifier.change_category` plus the relevant `posts.add_guidesection` / `posts.change_guidesection` rights |
| Manage sections and article placements | Relevant add/view/change permissions for both `guidesection` and `guidesectionarticle`; category view for category autocomplete; existing article visibility |
| Delete a section containing placements | `posts.delete_guidesection` and `posts.delete_guidesectionarticle`; visibility of every referenced article |
| Full section history | Section view/change plus global `posts.view_post` or `posts.change_post` |

Change permission also satisfies the corresponding view check. Deletion is
optional for a curator: withhold delete rights if unnecessary. Category/subtree
deletion additionally requires Django's related-object permissions and repeats
placement visibility checks, including confirmed bulk actions.

`posts.change_own_post` keeps article selection and submitted placement choices
within the user's own articles. Such editors can preview only when all eligible
articles are in their scope; mixed-author previews return 403. Global
`posts.view_post` deliberately expands article visibility, including unpublished
articles in Admin, so approve that scope explicitly. No permission assignments
were changed during release preparation.

## Server acceptance before pilot activation

Test with actual restricted accounts, not just a superuser, through the public
reverse proxy:

1. An existing catalog and its `/list/` still render normally; an existing
   article retains its original URL, canonical, publisher and category.
2. A staff viewer with all preview permissions can preview a saved real
   collection. Missing permissions and out-of-scope eligible articles return
   403; anonymous users redirect to Admin login. Do not enable public access to
   Admin or bypass the existing proxy authentication policy.
3. Preview success, login redirect and handled errors carry
   `X-Robots-Tag: noindex, nofollow`, private/no-store/no-cache directives,
   expired `Expires`, and `Vary: Cookie`. The proxy/CDN must honor these and
   bypass caching for Admin. HTML preview has noindex and public canonical.
4. Hidden sections/posts/category ancestry are absent from the preview and
   public collection. Restricted users cannot disclose hidden article titles
   through deletion confirmations or section history.
5. After content approval, activate only the intended real pilot category by
   selecting `guide_hub`. Check section/article order, links, unique article
   count, canonical and sitemap eligibility. Its `/list/` responds with an
   uncached temporary 302. No local demo records are part of this step.

## Recovery

For a presentation problem, set the pilot category back to `catalog`; guide
sections and placements remain available, and `/list/` pagination returns.
For an application regression, prefer restoring the previous application image
while retaining the additive schema and curation data.

Schema reversal is destructive to Guide Hub curation. Only with a verified
backup and a separate explicit rollback decision, stop new-code workers, inspect
the reverse migration plan, roll `posts` back to `0034`, then `classifier` to
`0014`, and run the old application. Referenced articles and existing categories
survive, but section/placement rows and presentation choices are lost; a later
forward migration does not restore them. Inspect dependent migrations if the
schema has evolved beyond these leaves.

## Local verification — 2026-10-17

All 102 tests passed: 88 Guide Hub tests and 14 classifier model tests in
isolated PostgreSQL. They covered forward/reverse migration preservation,
public eligibility/rendering, admin permissions, preview privacy, deletion/title
regressions, sitemap eligibility and reversible redirects. Models produced no
pending migrations; local migration plan was empty. Local standard Guide Hub
permissions existed and no groups had them assigned. System checks reported the
existing CKEditor 4 and non-unique login-email warnings, with no errors.

Server schema state, deployment revision, proxy behavior and real editor role
assignments remain acceptance gates; no server actions were performed.
