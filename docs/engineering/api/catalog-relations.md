# Editorial catalog relations API

The private API under `/api/content/catalog/` exposes version 1 of the shared catalog relation model. It uses the existing `Authorization: Token <token>` authentication. An active staff user needs `catalog.view_relationrecord`, an explicit site grant and grants for every participant in the record’s history. The server’s configured `SITE_ID` selects the site. Responses carry `Cache-Control: no-store` and `X-Robots-Tag: noindex, nofollow`.

Draft creation additionally requires `catalog.add_relationrecord` and `can_edit`. Appending a revision, submitting and archiving require `catalog.change_relationrecord` and `can_edit`. Review requires `catalog.review_relationrecord` and `can_review`. Release and unrelease require `catalog.publish_relationrecord` and `can_publish`. Shared review and archive follow the same additional site capabilities as Django Admin. All mutations call the shared `RelationAccess` policy and relation service.

## Provisioning access in Django Admin

An active superuser can provision access under **Catalog**. Each save or removal uses the Django Admin log.

1. Create a **Relation site grant** for the staff account. The form offers the configured site. Enable the edit, review and publish capabilities the account needs.
2. Add a **Relation entity grant** under that site grant for each required participant. Select the existing crop category or preparation or problem post to derive its catalog entity, or enter the entity UUID directly. The form checks that a supplied UUID matches the selected anchor. An anchor without a catalog entity requires catalog identity setup first.
3. To authorize review of plant-protection applications, select an active **Application country policy** in **Application reviewer grants** and enable **Can review**. If the policy is missing, configure its country code and verified IANA timezone under **Application country policies** first. The Ukraine policy uses `UA` and `Europe/Kyiv`.

The account also needs the Django model permissions for its assigned actions. The country grant authorizes review only when the site grant and review permissions allow it. Removing a site grant removes its entity and application reviewer grants.

## Provisioning an entity and its grant through the API

`POST /api/content/catalog/entities/provision/` requires a token belonging to an active staff superuser. Supply the primary key of an existing **Relation site grant** on the configured `SITE_ID`, and the primary key and type of an existing category or post.

```json
{
  "site_grant_id": 1,
  "anchor_type": "post",
  "anchor_id": 123,
  "kind": "preparation",
  "provenance": {
    "formulation_identity": "example-registration-record",
    "reference": "https://example.org/register"
  }
}
```

For a category use `"anchor_type": "category"` and `"kind": "crop"`. For a new identity send a non-empty provenance object, up to 16 KiB. A preparation needs a stable `formulation_identity` that the application review can later match to its evidence. To select a known, active identity explicitly, supply its `entity_id` in place of `provenance`. Establish the identity from the source materials before creating it.

The operation atomically creates or resolves the identity, binds the anchor and adds its grant. It records changes in the Django Admin log under the token's operator. The response includes `site_id`, `site_grant_id`, `entity_id`, `entity_grant_id`, `anchor_type`, `anchor_id` and `kind`. An identical retry resolves to the same IDs. Creation returns 201 and reuse returns 200. An incompatible existing identity or provenance returns 409. A site grant from another site returns 404.

Provisioning is private. Content approval, approved presentation, application review and seller publication have their own workflows.

## Routes

| Method and suffix | Representation or action |
| --- | --- |
| GET `entity-types/` | Entity kind codes and labels |
| GET `relation-types/` | Cursor-paginated versioned schemas, roles, cardinalities and identity fields |
| GET `entities/` | Authorized active participants, label anchors and kind |
| POST `entities/provision/` | Provision an anchored identity and an entity grant under a configured-site grant |
| GET, POST `relations/` | Cursor-paginated records or create a draft |
| GET `relations/{record}/` | Latest revision, state, current-site release pointer and ETag |
| DELETE `relations/{record}/` | Archive and disable releases, preserving history |
| GET, POST `relations/{record}/revisions/` | Cursor-paginated immutable history or append a full draft |
| POST `revisions/{revision}/submit/` | Submit the specified draft |
| POST `revisions/{revision}/review/` | Approve or reject the specified submitted revision |
| POST `relations/{record}/release/` | Release a specified approved revision on the current site |
| POST `relations/{record}/unrelease/` | Disable the current-site pointer, including when a newer draft exists |
| POST `relations/{record}/archive/` | Explicit archive action, equivalent to DELETE |
| GET `relations/{record}/audit/` | Cursor-paginated actions with actor, time and revision |
| GET `operations/{key}/` | Read the authenticated actor/site’s original create/revision result |

The generic editorial lifecycle supports `related_to` and `cultivar_of`. The `plant_protection_application` domain adapter additionally requires explicit country review authority, formulation/source verification and country-calendar validity. See [application fields and workflow](plant-protection-applications.md). Other schemas remain discoverable and can receive schema-valid private drafts. Their review/release actions require their owning domain adapters. Entity search uses existing identities and grants. Identity corrections, global source withdrawal/reinstatement, import batches, block configuration and public catalog selection have separate owning policies/tasks in the [accepted relations contract](../decisions/2026-11-15-catalog-relations-contract.md).

## Search and pagination

List responses contain `version`, `next`, `previous` and `results`. Follow the returned cursor URL with the same token. `page_size` defaults to 20 and accepts 1–50. Ordering uses stable unique IDs, with descending revision number inside one record. Every page reapplies the current site and participant grants. Final private responses are uncached.

`entities/?q=...&kind=cultivar&category=123` searches authorized post titles, category labels, kinds and post category labels. An exact UUID also matches. `schema=<schema-id>&role=<role>` restricts the selection to that schema role’s allowed kinds. Both parameters must be supplied together.

`relations/?entity=<uuid>&role=cultivar&type_code=cultivar_of` finds records containing that participant in the specified role. Omitting `role` includes all direct, reverse and multi-participant roles across retained revisions. Records are deduplicated before pagination. Unknown query parameters, invalid kinds/roles/types and invalid filter IDs return 400. An inaccessible entity returns 404. Invalid cursor tokens return 404.

## Create and revise

Discover or search authorized entity UUIDs before creating a draft. Example synthetic request body for `POST relations/` follows.

```json
{
  "type_code": "cultivar_of",
  "schema_version": 1,
  "participants": {
    "cultivar": ["11111111-1111-4111-8111-111111111111"],
    "crop": ["22222222-2222-4222-8222-222222222222"]
  },
  "payload": {"note": "Editorial relation"},
  "source": {"citation": "Reviewed editorial source"}
}
```

Creation requires `Idempotency-Key: catalog-create-001`. Success returns 201, `version: 1`, `record`, `revision_id` and an `ETag` header such as `"<record-uuid>:1"`. Read the actual ETag from the response. Send the complete draft body to `POST relations/{record}/revisions/` with a new `Idempotency-Key` and `If-Match` containing the record’s current ETag. `country` and `source_version_digest` are optional as a pair. When present, they require an uppercase two-letter country and a lowercase 64-character hexadecimal source digest.

Top-level unknown fields are rejected. NUL characters and unpaired Unicode surrogates in nested JSON keys or values are rejected before database access. The same text checks apply to search filters and operation readback keys. Lifecycle state, reviewer, site and release flags cannot be assigned through a draft request. Material edits append a revision. A changed semantic identity returns 409 and requires the owning explicit correction workflow. A newer draft preserves the existing approved site release.

Create and revision requests reuse immutable `ImportReceipt` storage in the namespace `editorial-api:v1:<site>:<actor>`. The digest includes the normalized body, route and original `If-Match`. The receipt and mutation commit in one transaction. Concurrent identical requests produce one revision and one receipt. Repeating the same key and input returns the original 201 body and ETag with `Idempotent-Replay: true`, after checking current write and participant access. Read the record again for its latest ETag. Another payload or route under that key returns 409 `idempotency_conflict`. A duplicate semantic relation under a new key returns 409 `duplicate_relation` with a scoped generic message.

After an uncertain transport outcome, read `operations/{key}/` or repeat the original request with the same key, body and original If-Match. The operation readback also checks current participant access. A failed transaction produces neither a partial revision nor a receipt.

## Lifecycle and concurrency

Every lifecycle POST and DELETE requires the current record ETag in `If-Match`. Missing preconditions return 428 `missing_precondition`. A stale or mismatched token returns 409 `stale_version` and leaves state intact. Storage rechecks the version under its transaction locks. The shared transaction-scoped graph lock coordinates API, Admin and presentation-selection writes.

Submit and archive take `{}`. Review takes `{"action":"approve","content_locale":"uk"}` or `{"action":"reject"}`. Release takes `{"revision_id":"<approved-revision-uuid>","content_locale":"uk"}`. Unrelease takes `{}` and targets the current site’s live pointer. Approval and release recheck every participant’s approved current publication, site, content language, category ancestry, canonical path and material review evidence. A changed or hidden participant fails the gate. A publisher can still unrelease after a participant becomes unavailable. Archive checks publisher capability on every site in the release history.

## Errors and compatibility

Error responses contain `{"version":1,"error":{"code":"...","detail":...}}`. Validation uses 400, authentication 401, denied capabilities 403, invisible scoped resources 404, stale/semantic/idempotency conflicts 409 and missing preconditions 428. Detail may contain field errors or messages. Clients should branch on status and `error.code`.

The catalog routes extend the existing content namespace. Existing content ownership, parser token policies, post payloads and Product matching continue through their established endpoints.

Application record withdrawal/reinstatement actions are documented with their additional domain, country and global site authority in [the application workflow](plant-protection-applications.md). Record responses expose the latest withdrawal reference, reason and evidence within the existing private record scope.

Shared [bulk operations](catalog-batches.md) provide read-only preview, atomic draft/lifecycle apply, actor/site-bound receipts and source-batch withdrawal/reconciliation through the same policy and storage service. The Django Admin entry point is **Catalog → Relation records → Bulk operations**.
