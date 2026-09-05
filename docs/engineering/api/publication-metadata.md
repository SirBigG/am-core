# Publication metadata API

Publication metadata belongs to `Post`. Catalog `title` remains the canonical
entity name used by lists, breadcrumbs, matching, Agromarket and image alt text.
`meta_title` supplies both the document title and article H1. It does not rename
the cultivar/breed, alter its slug or modify its URL.

## Fields and defaults

| Field | Writable | Meaning |
| --- | --- | --- |
| `title` | Yes | Required canonical entity name. |
| `meta_title` | Yes | Optional plain-text override, at most 500 characters. |
| `meta_description` | Yes | Optional plain-text description, at most 500 characters. |
| `resolved_metadata` | No | Object containing the effective `title` and `description`. |

Omitting an optional field in PATCH preserves its current value. Send `null`,
`""` or whitespace to clear it. The API trims leading/trailing whitespace.
Empty metadata fields resolve independently: title falls back to `Post.title`,
description falls back to the first 160 characters of normalized article text
with HTML removed and entities decoded. An empty article produces an empty
fallback description. Explicit descriptions are not silently truncated.

`resolve_publication_metadata()` in `core/posts/metadata.py` owns this rule.
The same output drives HTML title, H1, description, Open Graph, Twitter,
Article JSON-LD, native sharing title and `resolved_metadata` in the content API.
The old related `MetaData` record is never a runtime fallback, so clearing a
field cannot unexpectedly resurrect an archived value.

Primary publication photos remain the social images; missing photos use the
existing site default. Canonical URLs are generated from the publication's
existing absolute URL and public host, without query parameters. HTML canonical,
Open Graph URL and Article mainEntityOfPage agree even on a route alias. Robots,
publication dates, authors, breadcrumbs and FAQ schema keep their existing rules.
No custom canonical URL, robots, keywords or social-image fields are introduced.

## Endpoints and authorization

- `GET /api/content/posts/`: token-authenticated listing, including raw and
  resolved metadata. Existing rubric/country filters and pagination still apply.
- `POST /api/content/posts/`: token-authenticated creation. `title`, `text` and
  `rubric` remain required; metadata is optional. Publisher is the token owner.
- `GET`, `PATCH`, `PUT /api/content/posts/<id>/`: staff token required; existing
  publisher protection and permissions are unchanged.
- `OPTIONS /api/content/posts/`: describes the fields, optionality and maximum
  lengths for clients and skills.

A metadata-only update:

```http
PATCH /api/content/posts/460/
Authorization: Token <token-from-runtime-environment>
Content-Type: application/json
```

```json
{
  "meta_title": "Голден Делішес: опис сорту та характеристики",
  "meta_description": "Характеристики сорту Голден Делішес, особливості плодів, запилення та вирощування."
}
```

The returned resource still has `title: "Голден Делішес"`, its existing slug/URL,
and `resolved_metadata` containing the two configured strings. To restore defaults:

```json
{"meta_title": null, "meta_description": null}
```

Existing content API clients remain compatible. `page_h1` was not part of this
API and is replaced internally by `meta_title`; clients should use the documented
fields. `meta`, metadata record IDs and `resolved_metadata` are not writable API
configuration. Read-only inputs follow existing DRF behavior and are ignored.

The content-refresh client accepts the new field in its ordinary PATCH payload.
Mutable snapshot checksums now include `meta_title` alongside `meta_description`;
resolved output is excluded. Re-inventory old review/snapshot bundles before
publishing: old checksums intentionally do not bypass detection of metadata edits.
Future skills should read the current resource, patch only intended raw fields,
and compare both raw and resolved values in the response.

## Migration and rollback

Migration `posts.0034_direct_publication_metadata` renames `page_h1` to
`meta_title` without discarding values. It fills a blank title from the old
`MetaData.title`, then `MetaData.h1` if necessary; it fills a blank direct
description from the old description. Nonblank direct values always win.
The description limit expands from 250 to 500, preserving old 255-character
metadata descriptions. No content dates or identity fields are updated.

The old `Post.meta` relation and related rows remain a non-editable migration
archive. They disappear from the publication admin form and public query/render
path; deleting such an archived row no longer cascades into deleting its post.
Categories and other users of MetaData retain their own existing workflows.
A later cleanup can remove the archive after retention/rollback needs are met.

Deploy with a database backup and a coordinated code/migration release: the
column rename requires stopping old workers before migrating and starting new
workers afterwards. It is not a rolling-compatible column rename. New code on an
unmigrated database, or old code on the renamed schema, will fail.

The reverse migration renames the title column back but deliberately does not
undo copied values or create/update legacy records. Reverting the old 250-character
description limit can fail if new longer descriptions exist. Restore from a
pre-release backup for an exact rollback, or review/export later edits and resolve
oversized descriptions before reversing. Legacy rows alone are not an exact
snapshot of all post fields.

## Local verification, 2026-09-05

69 focused Django tests passed across the metadata resolver/rendering, API,
admin, schema/data migration, Post model, existing detail page, content refresh
and Agromarket. Tests cover blank/null/whitespace defaults, independent overrides,
HTML/JSON escaping, canonical alias paths, photo defaults, permissions, validation,
API OPTIONS, metadata checksums, migration precedence and unchanged identity/dates.

`makemigrations --check --dry-run` reported no changes. Local migration succeeded.
Before/after comparison covered all 3270 local posts: three legacy metadata records
(39, 40, 42) were copied; titles, slugs, URLs, dates, legacy references and existing
direct descriptions were preserved. Local evidence lives in
`/tmp/agromega-metadata/before.json` and `after.json`.

Browser verification confirmed post 39 keeps catalog name “Брама”, while its
HTML title, H1, OG title, Twitter title and share title all use the migrated
“Порода курей Брама”. Admin displays the two direct optional fields in its own
metadata section and has no linked-record picker. Existing Golden Delicious
provides the empty-metadata fallback case. No content was manually rewritten.

No production migration/deployment, external crawler validation or full-project
test suite was performed. Existing CKEditor, non-unique email and naive-datetime
warnings remain outside this change.
