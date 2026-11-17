# Plant-protection application domain extension

`plant_protection_application/v1` extends the [catalog relations API](catalog-relations.md) and the same Django Admin forms. `PlantProtectionApplicationDetails` is an immutable OneToOne projection of `RelationRevision`. Participants, identity, history, releases, receipts, source withdrawal gates and audit use the shared catalog models and services.

This delivery supplies the domain storage and existing private Admin/API integration. AGRO-76 owns bulk import, AGRO-78 owns the public selector, AGRO-80 owns block configuration and AGRO-81 owns page rendering. Those components remain required for full AGRO-85 acceptance. No public application endpoint or automatic page block is enabled by this migration.

## Identity and source

An application requires one `preparation`, one `crop` and zero or one `target`. Exact targets have kind `disease`, `pest` or `weed`. Their `target_kind` must match, `target_locator` must be empty and `target_text` must be null. A grouped or uncertain source target has no target participant, an explicit normalized source locator and literal source text. Its `target_kind` can also be `other`. Source text never creates additional participants.

Identity includes participant UUIDs, country, method, formulation identity, source target locator, registration authority/key and application locator. Different methods and regulations are separate records. A different preparation or target identity requires the explicit correction workflow. Formulation identity must match the immutable preparation entity’s `provenance.formulation_identity` before approval. The domain reviewer also verifies independent formulation provenance on the application revision. Equal active ingredients confer no relation or permission.

Source contains exactly `reference`, `document`, `version` and `content_digest`. The latter is a lowercase SHA-256 digest of the reviewed source content. The writer derives the canonical source-version digest with the shared PostgreSQL `catalog_identity_digest(source::jsonb)` function and binds it to the explicit payload country. A supplied top-level country or source-version digest must match the derived scope. A new source version creates a new draft and retains prior evidence and approval history.

## Synthetic draft example

Use existing authorized entity UUIDs from discovery. The following example expresses software test data and supplies no real agronomic or regulatory assertion.

```json
{
  "type_code": "plant_protection_application",
  "schema_version": 1,
  "participants": {
    "preparation": ["11111111-1111-4111-8111-111111111111"],
    "crop": ["22222222-2222-4222-8222-222222222222"],
    "target": ["33333333-3333-4333-8333-333333333333"]
  },
  "payload": {
    "country": "UA",
    "method": "foliar_spray",
    "formulation_identity": "synthetic-formulation-A",
    "formulation_verified": null,
    "formulation_provenance": {},
    "target_kind": "disease",
    "target_locator": "",
    "registration_authority": "synthetic-authority",
    "registration_record_key": "synthetic-registration",
    "application_locator": "application-1",
    "checked_at": null,
    "valid_from": null,
    "valid_until": null,
    "regulatory_decision": "unresolved",
    "regulatory_provenance": {}
  },
  "source": {
    "reference": "urn:agro:synthetic-source",
    "document": "synthetic-document",
    "version": "1",
    "content_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
}
```

Create with a new `Idempotency-Key`. Revisions and lifecycle actions require the record’s current `If-Match`, as documented for the shared API. In Django Admin choose the application schema, select its participants and enter the same payload/source JSON. The canonical country and source digest appear in the stored revision. History exposes the immutable evidence to authorized viewers and reviewers.

Method codes belong to `ApplicationMethod`. Migration bootstrap adds `foliar_spray`, `soil_application` and `seed_treatment`. A further controlled method is data configuration and requires no crop-specific branch. This pilot stores applications without doses. Dose fields are rejected and require a separately defined unit/method validation contract before support.

## Review and release

Unknown formulation verification and validity bounds remain null. Regulatory decision is explicit `unresolved`, `confirmed`, `denied` or `expired`. Approval requires verified formulation evidence, matching preparation provenance, regulatory decision `confirmed` with provenance, a check timestamp no later than now and known ordered validity bounds. Drafts can retain incomplete verification while their logical identity and source are known.

The actor needs the shared reviewer permission and site capability, `catalog.review_plant_protection_applications` and an explicit `ApplicationReviewerGrant` for that site grant and country. A multi-site review requires the existing shared-review capability and the same country authority on every affected site. No review, publisher or country grants are seeded.

`ApplicationCountryPolicy` supplies the verified IANA timezone and an explicit active flag. Unknown or inactive country policy fails closed. Publishers use the existing site publish capability. Release repeats domain evidence and participant publication/site/content-language checks. Validity dates are inclusive in the configured country calendar. A date D qualifies through its local end of day. Fresh evaluation after expiry requires no save. The future public selector must perform the same domain/date/source gates on every request before counts and pagination.

A source contradiction or revoked permission requires the accepted explicit global withdrawal workflow. Draft editing and site unrelease retain their narrower lifecycle meanings. Record withdrawal and reinstatement use the shared storage operations through explicit domain policy. `POST relations/{record}/withdraw/` takes `reason` and nonempty structured `evidence`, requires `catalog.withdraw_relation`, the current ETag and an `Idempotency-Key`. It verifies country review authority and publisher access to all historical participants on every released site. Multiple sites also require the shared-review capability. The response includes the stable `withdrawal_id` and current record. Replaying the same key and original If-Match returns that withdrawal reference without incrementing the epoch again. A conflicting payload or stale request under a new key cannot overwrite another decision.

`POST relations/{record}/reinstate/` takes `revision_id`, `withdrawal_id` and nonempty resolution `evidence`, requires `catalog.reinstate_relation` and the current ETag. It repeats the global authority checks and requires a newly approved current-epoch revision whose check time follows the withdrawal. Reinstatement leaves all releases disabled. The publisher separately releases the current eligible revision. Source gates and quarantine remain authoritative.

Django Admin offers **Withdraw globally** and **Reinstate after review** for the corresponding explicit permissions. The form collects decision evidence and reason, and shows the current withdrawal decision and event reference. Schema fields and publication policy are shared with the API. The shared [batch-operation workflow](catalog-batches.md) now provides draft imports and source-level withdrawal/quarantine/reconciliation with explicit manifests, preview, atomic apply and receipt readback.

## Database and recovery

Migration 0009 adds the typed projection, controlled methods, country configuration and reviewer grants. Migration 0010 bootstraps the immutable type schema and deferred PostgreSQL guards. Repeated bootstrap verifies the exact schema and creates no real catalog mappings. Existing Post, Category, Product and Guide records are untouched.

Guards require a typed projection for every application revision, mirror its payload/source/country, validate target meaning and source identity, retain immutable evidence and require complete evidence before approval. Release guards enforce current country-calendar validity. Shared role/kind/sealing/identity/unique/fence guards remain in force. OneToOne projection is unique per revision and shared semantic uniqueness prevents duplicate records, including concurrent creates.

The SQL guard migration has a reverse operation for isolated migration rehearsals. Production removal of the projection tables would discard their data and requires an explicit maintenance decision. Feature disable uses inactive country policy and site unrelease while retaining history. Re-enabling the policy still requires current domain/source/publication eligibility. Global withdrawal epochs and blocked source digests retain their own durable gates.
