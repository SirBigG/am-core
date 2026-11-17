# Catalog bulk operations

The shared batch service supports private catalog draft imports, explicit lifecycle changes, archive and plant-protection source withdrawal/reconciliation. API and Django Admin call the same `CatalogBatch` service, `RelationAccess` policy and storage operations. Authentication and permissions follow the [catalog API](catalog-relations.md).

## Workflow

1. Choose one operation, a stable operation key and explicit item keys/participants/record IDs. A batch contains at most 50 items. Each existing record is selected once.
2. Request a read-only preview. It returns exact create/revise/noop/status effects, before/after content, duplicate references and errors. It performs no catalog INSERT, UPDATE or DELETE.
3. Review the result and apply the returned signed preview with its payload digest. First apply requires a preview issued within 15 minutes. `CATALOG_BATCH_PREVIEW_MAX_AGE` configures the lifetime in seconds.
4. Read the immutable receipt. Follow its result cursor or the current record link. For an uncertain transport outcome, repeat the original apply or read its known receipt ID. Retain each batch’s operation key when resuming a larger import.

Apply is atomic within one batch. An error rolls back all record/revision/audit/receipt changes in that batch. Separate batches have separate receipts. Inputs never perform automatic title/category/source matching.

The signed preview binds the authenticated actor, configured site, normalized input, schemas, selected mappings, relevant material/policy and base record state. Apply clears permission caches, rereads current authority, acquires the shared editorial graph/type/record locks and rebuilds the preview before writing. Changed state or revoked authority prevents application. Preview neither reserves a record nor grants future rights.

## API

| Route | Behavior |
| --- | --- |
| POST `/api/content/catalog/imports/dry-run/` | Validate and preview a batch |
| POST `/api/content/catalog/imports/apply/` | Apply the signed preview and digest |
| GET `/api/content/catalog/imports/{receipt_id}/` | Current-authority-checked, cursor-paginated receipt |

All responses are private, no-store and noindex. Receipt pages default to 20 items and accept `page_size` from 1 to 50. Follow the relative `next` URL. Cursors are signed and bound to the receipt. Results are ordered by unique item key.

### Draft batch

```json
{
  "operation": "drafts",
  "operation_key": "catalog-import-001",
  "items": [
    {
      "key": "row-001",
      "draft": {
        "type_code": "cultivar_of",
        "schema_version": 1,
        "participants": {
          "cultivar": ["11111111-1111-4111-8111-111111111111"],
          "crop": ["22222222-2222-4222-8222-222222222222"]
        },
        "payload": {},
        "source": {"reference": "synthetic reviewed source"}
      }
    }
  ]
}
```

Use real authorized UUIDs discovered through the private participant API. The example identifiers and source are synthetic. For an explicit revision, add `record_id` and its current `if_match` ETag alongside `draft`. The draft body uses the same schema fields as the single-record API. Application drafts use the [typed application fields](plant-protection-applications.md).

Imports create drafts only. Lifecycle/status/reviewer/site keys outside the documented fields are rejected. An exact existing latest revision is a noop. Identical logical drafts repeated in one batch resolve to the first item. Canonical JSON comparisons preserve distinctions such as boolean `true` and numeric `1`. Conflicting content under the same logical key requires an explicit versioned revision or identity correction. Inactive identities retain their recovery gates. Noop and receipt replay never approve, reinstate or publish anything.

### Lifecycle batches

Choose `submit`, `approve`, `reject`, `publish`, `unpublish` or `archive`. Each item carries `key`, `record_id` and its current `if_match` ETag. Submit/review/publish also require `revision_id`. Approve and publish require `content_locale`; reject may omit it. Unpublish targets the actual current-site release pointer, including when a newer draft exists. Archive disables the record’s releases through the existing publication-aware policy.

```json
{
  "operation": "submit",
  "operation_key": "catalog-submit-001",
  "items": [
    {
      "key": "row-001",
      "record_id": "33333333-3333-4333-8333-333333333333",
      "revision_id": "44444444-4444-4444-8444-444444444444",
      "if_match": "\"33333333-3333-4333-8333-333333333333:2\""
    }
  ]
}
```

Preview applies the same role, source, epoch, approved-base, domain/country, site and participant publication checks as the corresponding single-record action. It does not write the transition. Apply repeats those checks. A draft import supplies no review or publisher capability. Pure revision batches require change permission; mixed create/revision batches require both add and change permissions.

### Apply and readback

```json
{
  "preview": "<signed preview returned by dry-run>",
  "payload_digest": "<SHA-256 returned by dry-run>"
}
```

The apply response identifies the receipt and per-item effects, record/revision references and resulting ETags. `Idempotent-Replay` distinguishes a completed replay. Receipts use immutable `ImportReceipt` storage in an actor/site-specific namespace. The operation key and payload digest protect against a different payload reusing that key. The receipt commits in the same transaction as its changes. A completed replay may be read after preview expiry because it performs no new mutation, while current permissions and participant access are checked again.

A receipt describes the original execution outcome at `completed_at`. Read the record endpoint for its current version, withdrawal and publication state before starting another operation. A historical receipt does not certify current eligibility.

Malformed batch structure is rejected with 400. The preview can also report per-item validation/conflict errors with `can_apply=false`. Such a preview cannot be applied. Stale, expired, changed-input or conflicting apply returns 409; denied authority returns 403 and inaccessible receipt/record scope returns 404. The shared catalog error envelope remains version 1.

## Source batches for applications

A source batch selects one canonical source version or country quarantine. Its total affected record scope is limited to 50. It uses the existing global source service, domain/country grants and `withdraw_relation` permission. Publishers must cover the historical participants and sites of affected records. Multi-site scope additionally requires shared-review authority. Incomplete-scope quarantine and reconciliation always require platform shared-review authority.

`withdraw_source` has one item with `key`, `type_code: plant_protection_application`, `country`, `source_version_digest`, `reason`, structured `evidence`, explicit `scope_complete`, `affected_versions` and `scope_versions`.

- `affected_versions` maps every record whose history references the selected country/source digest to its current lock version.
- For a complete source scope, `scope_versions` is empty.
- For an incomplete scope, `scope_versions` maps every currently released record in that type/country to its current version, including records from other source versions that quarantine will disable.

Preview displays the exact current manifests and before/after effects. A mismatched manifest remains non-applicable until the editor selects and previews the exact set. Source withdrawal atomically creates the durable source gate, disables affected releases and advances each source record’s withdrawal epoch. Incomplete scope also establishes the country/type quarantine and disables its other releases. Future imports of the blocked digest fail. A racing import either changes the manifest and makes withdrawal require a fresh preview, or observes the committed source gate and fails. Partial source withdrawal is never committed.

`reconcile_source` has one item with `key`, application `type_code`, `country`, `if_match`, `affected_versions` and structured resolution `evidence`. Use the scope ETag from the receipt or preview and the full current country/type record manifest. The action clears only the reviewed quarantine. Source gates stay blocked, withdrawn records stay withdrawn and every release stays disabled. Positive restoration/release retains its separate domain gates.

## Django Admin

Open **Catalog → Relation records → Bulk operations**. Enter the same explicit batch JSON, select **Preview**, review each before/after effect and error, then choose **Apply reviewed batch**. The signed confirmation is tied to that user/site and expires after the configured lifetime. Receipt pages link the changed records and show their execution references. They use the same access checks and pagination as the API.

## Evidence and rollout

The source lookup index covers country/source digest/record. The implementation adds no real mappings or grants. Local tests use disposable PostgreSQL and synthetic entities/sources. General content/parser ownership and Product matching continue through their established endpoints. Public related-catalog selection/configuration/rendering remains owned by AGRO-78/80/81.
