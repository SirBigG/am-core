from django.db import migrations

# A single guard namespace for trusted transactional writers and direct SQL.
INSTALL = """
CREATE FUNCTION catalog_reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is immutable', TG_TABLE_NAME USING ERRCODE='23514';
END $$;

CREATE TRIGGER catalog_schema_immutable BEFORE UPDATE OR DELETE ON catalog_relationtypeversion
FOR EACH ROW EXECUTE FUNCTION catalog_reject_change();
CREATE TRIGGER catalog_type_immutable BEFORE UPDATE OR DELETE ON catalog_relationtype
FOR EACH ROW EXECUTE FUNCTION catalog_reject_change();
CREATE TRIGGER catalog_kind_immutable BEFORE UPDATE OF kind ON catalog_catalogentity
FOR EACH ROW WHEN (OLD.kind IS DISTINCT FROM NEW.kind) EXECUTE FUNCTION catalog_reject_change();
CREATE TRIGGER catalog_audit_append_only BEFORE UPDATE OR DELETE ON catalog_relationauditevent
FOR EACH ROW EXECUTE FUNCTION catalog_reject_change();
CREATE TRIGGER catalog_withdrawal_append_only BEFORE UPDATE OR DELETE ON catalog_relationwithdrawal
FOR EACH ROW EXECUTE FUNCTION catalog_reject_change();
CREATE TRIGGER catalog_correction_append_only BEFORE UPDATE OR DELETE ON catalog_relationidentitycorrection
FOR EACH ROW EXECUTE FUNCTION catalog_reject_change();
CREATE TRIGGER catalog_source_gate_immutable BEFORE UPDATE OR DELETE ON catalog_sourcewithdrawalgate
FOR EACH ROW EXECUTE FUNCTION catalog_reject_change();
CREATE TRIGGER catalog_receipt_immutable BEFORE UPDATE OR DELETE ON catalog_importreceipt
FOR EACH ROW EXECUTE FUNCTION catalog_reject_change();

CREATE FUNCTION catalog_identity_digest(identity jsonb) RETURNS text
LANGUAGE sql IMMUTABLE STRICT AS $$
    SELECT encode(sha256(convert_to(identity::text, 'UTF8')), 'hex')
$$;

CREATE FUNCTION catalog_guard_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Relation history must be retained' USING ERRCODE='23514';
    END IF;
    IF NEW.identity_digest IS DISTINCT FROM catalog_identity_digest(NEW.identity) THEN
        RAISE EXCEPTION 'Invalid semantic identity digest' USING ERRCODE='23514';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF ROW(OLD.id, OLD.relation_type_id, OLD.identity, OLD.identity_digest, OLD.created_by_id, OLD.created_at)
            IS DISTINCT FROM
            ROW(NEW.id, NEW.relation_type_id, NEW.identity, NEW.identity_digest, NEW.created_by_id, NEW.created_at)
           OR NEW.eligibility_epoch < OLD.eligibility_epoch
           OR (OLD.superseded_by_id IS NOT NULL AND
               (NEW.superseded_by_id IS DISTINCT FROM OLD.superseded_by_id OR NOT NEW.withdrawn OR NOT NEW.archived))
           OR NEW.lock_version < OLD.lock_version THEN
            RAISE EXCEPTION 'Invalid relation record update' USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER catalog_record_guard BEFORE INSERT OR UPDATE OR DELETE ON catalog_relationrecord
FOR EACH ROW EXECUTE FUNCTION catalog_guard_record();

CREATE FUNCTION catalog_guard_revision() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Relation revision must be retained' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM catalog_relationrecord WHERE id=NEW.record_id FOR UPDATE;
    IF NOT ((NEW.country='' AND NEW.source_version_digest='') OR
            (NEW.country ~ '^[A-Z]{2}$' AND NEW.source_version_digest ~ '^[a-f0-9]{64}$')) THEN
        RAISE EXCEPTION 'Invalid source version scope' USING ERRCODE='23514';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.state <> 'draft' OR NEW.sealed OR NOT EXISTS (
            SELECT 1 FROM catalog_relationrecord
             WHERE id=NEW.record_id AND eligibility_epoch=NEW.created_epoch AND superseded_by_id IS NULL
        ) THEN
            RAISE EXCEPTION 'New revision must be a draft at the current epoch' USING ERRCODE='23514';
        END IF;
    ELSIF (to_jsonb(OLD) - ARRAY['sealed','state','approval_epoch','reviewed_by_id','reviewed_at'])
        IS DISTINCT FROM
        (to_jsonb(NEW) - ARRAY['sealed','state','approval_epoch','reviewed_by_id','reviewed_at'])
        OR (OLD.sealed AND NOT NEW.sealed)
        OR (OLD.state IN ('approved','rejected') AND ROW(OLD.state, OLD.approval_epoch,
            OLD.reviewed_by_id, OLD.reviewed_at) IS DISTINCT FROM
            ROW(NEW.state, NEW.approval_epoch, NEW.reviewed_by_id, NEW.reviewed_at))
        OR (OLD.state <> NEW.state AND
            NOT ((OLD.state='draft' AND NEW.state='submitted')
                OR (OLD.state='submitted' AND NEW.state IN ('approved','rejected'))))
        OR (OLD.state <> NEW.state AND NOT EXISTS (
            SELECT 1 FROM catalog_relationrecord WHERE id=NEW.record_id
                AND eligibility_epoch=NEW.created_epoch AND superseded_by_id IS NULL AND NOT archived
        ))
    THEN
        RAISE EXCEPTION 'Invalid revision transition or immutable content changed' USING ERRCODE='23514';
    END IF;
    IF TG_OP='INSERT' OR OLD.state IS DISTINCT FROM NEW.state THEN
        IF EXISTS (
            SELECT 1 FROM catalog_relationrecord r
            JOIN catalog_sourcewithdrawalgate g ON g.relation_type_id=r.relation_type_id
                AND g.country=NEW.country AND g.source_version_digest=NEW.source_version_digest
            WHERE r.id=NEW.record_id
        ) OR EXISTS (
            SELECT 1 FROM catalog_relationrecord r
            JOIN catalog_relationscopegate g ON g.relation_type_id=r.relation_type_id
                AND g.country=NEW.country AND g.quarantined WHERE r.id=NEW.record_id
        ) THEN
            RAISE EXCEPTION 'Source version or scope is withdrawn' USING ERRCODE='23514';
        END IF;
    END IF;
    IF TG_OP='UPDATE' AND OLD.state='submitted' AND NEW.state='approved' AND
        NEW.base_approved_revision_id IS DISTINCT FROM (
            SELECT v.id FROM catalog_relationrevision v WHERE v.record_id=NEW.record_id
                AND v.state='approved' AND v.approval_epoch=NEW.created_epoch
            ORDER BY v.number DESC LIMIT 1
        ) THEN
        RAISE EXCEPTION 'Approval base changed' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER catalog_revision_guard BEFORE INSERT OR UPDATE OR DELETE ON catalog_relationrevision
FOR EACH ROW EXECUTE FUNCTION catalog_guard_revision();

CREATE FUNCTION catalog_guard_participant() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'Participants are immutable' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM catalog_relationrevision WHERE id=NEW.revision_id AND NOT sealed FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Participants require an unsealed revision' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER catalog_participant_guard BEFORE INSERT OR UPDATE OR DELETE ON catalog_relationparticipant
FOR EACH ROW EXECUTE FUNCTION catalog_guard_participant();

CREATE FUNCTION catalog_validate_revision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    revision catalog_relationrevision;
    record catalog_relationrecord;
    definition catalog_relationtypeversion;
    projected_roles jsonb;
    projected_fields jsonb;
BEGIN
    SELECT * INTO revision FROM catalog_relationrevision WHERE id=NEW.id;
    SELECT * INTO record FROM catalog_relationrecord WHERE id=revision.record_id;
    SELECT * INTO definition FROM catalog_relationtypeversion WHERE id=revision.schema_id;
    IF NOT revision.sealed OR definition.relation_type_id IS DISTINCT FROM record.relation_type_id
        OR jsonb_typeof(revision.payload) <> 'object' OR jsonb_typeof(revision.source) <> 'object'
        OR (revision.base_approved_revision_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM catalog_relationrevision base WHERE base.id=revision.base_approved_revision_id
                AND base.record_id=record.id AND base.state='approved' AND base.number < revision.number
        )) OR EXISTS (
            SELECT 1 FROM catalog_relationparticipant p JOIN catalog_catalogentity e ON e.id=p.entity_id
            WHERE p.revision_id=revision.id
              AND NOT COALESCE(definition.roles -> p.role -> 'kinds' ? e.kind, false)
        ) OR EXISTS (
            SELECT 1 FROM jsonb_each(definition.roles) role
            CROSS JOIN LATERAL (
                SELECT count(*) AS total FROM catalog_relationparticipant p
                WHERE p.revision_id=revision.id AND p.role=role.key
            ) counts
            WHERE counts.total NOT BETWEEN (role.value->>'min')::int AND (role.value->>'max')::int
        ) OR EXISTS (
            SELECT 1 FROM catalog_relationparticipant WHERE revision_id=revision.id
            GROUP BY entity_id HAVING count(*)>1
        ) THEN
        RAISE EXCEPTION 'Incomplete or invalid relation revision' USING ERRCODE='23514';
    END IF;
    SELECT COALESCE(jsonb_object_agg(role, entities),'{}'::jsonb) INTO projected_roles
        FROM (
            SELECT role, jsonb_agg(entity_id::text ORDER BY entity_id) AS entities
            FROM catalog_relationparticipant WHERE revision_id=revision.id AND definition.identity_roles ? role
            GROUP BY role
        ) groups;
    SELECT COALESCE(jsonb_object_agg(key, revision.payload->key),'{}'::jsonb) INTO projected_fields
        FROM jsonb_array_elements_text(definition.identity_fields) AS keys(key);
    IF jsonb_build_object('roles',projected_roles,'fields',projected_fields) IS DISTINCT FROM record.identity THEN
        RAISE EXCEPTION 'Revision does not match record identity' USING ERRCODE='23514';
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER catalog_revision_integrity AFTER INSERT OR UPDATE ON catalog_relationrevision
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_validate_revision();

CREATE FUNCTION catalog_validate_releases() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE checked_record_id uuid;
BEGIN
    IF TG_TABLE_NAME='catalog_relationrecord' THEN checked_record_id=NEW.id;
    ELSE checked_record_id=NEW.record_id; END IF;
    IF EXISTS (
        SELECT 1 FROM catalog_relationrelease l JOIN catalog_relationrecord r ON r.id=l.record_id
            JOIN catalog_relationrevision v ON v.id=l.approved_revision_id
        WHERE l.record_id=checked_record_id
          AND (v.record_id<>r.id OR v.state<>'approved' OR NOT v.sealed OR
             (l.enabled AND (
                r.archived OR r.withdrawn OR r.superseded_by_id IS NOT NULL
                OR v.approval_epoch IS DISTINCT FROM r.eligibility_epoch
                OR EXISTS (
                    SELECT 1 FROM catalog_sourcewithdrawalgate g WHERE g.relation_type_id=r.relation_type_id
                      AND g.country=v.country AND g.source_version_digest=v.source_version_digest
                ) OR EXISTS (
                    SELECT 1 FROM catalog_relationscopegate g WHERE g.relation_type_id=r.relation_type_id
                      AND g.country=v.country AND g.quarantined
                )
             )))
    ) THEN
        RAISE EXCEPTION 'Invalid or ineligible relation release' USING ERRCODE='23514';
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER catalog_release_integrity AFTER INSERT OR UPDATE ON catalog_relationrelease
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_validate_releases();
CREATE CONSTRAINT TRIGGER catalog_record_release_integrity AFTER UPDATE ON catalog_relationrecord
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_validate_releases();

CREATE FUNCTION catalog_lock_release_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Release history must be retained' USING ERRCODE='23514';
    END IF;
    IF TG_OP='UPDATE' AND (OLD.record_id<>NEW.record_id OR OLD.site_id<>NEW.site_id
        OR OLD.lock_version>=NEW.lock_version) THEN
        RAISE EXCEPTION 'Release identity is immutable and version must advance' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM catalog_relationrecord WHERE id=NEW.record_id FOR UPDATE;
    RETURN NEW;
END $$;
CREATE TRIGGER catalog_release_lock BEFORE INSERT OR UPDATE OR DELETE ON catalog_relationrelease
FOR EACH ROW EXECUTE FUNCTION catalog_lock_release_record();

CREATE FUNCTION catalog_validate_correction() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE origin_id uuid;
BEGIN
    IF TG_TABLE_NAME='catalog_relationrecord' THEN origin_id=NEW.id;
    ELSE origin_id=NEW.original_id; END IF;
    IF EXISTS (
        SELECT 1 FROM catalog_relationrecord o
        LEFT JOIN catalog_relationidentitycorrection c ON c.original_id=o.id
        LEFT JOIN catalog_relationrecord s ON s.id=c.successor_id
        LEFT JOIN catalog_relationwithdrawal w ON w.id=c.withdrawal_id
        WHERE o.id=origin_id AND (
            o.superseded_by_id IS DISTINCT FROM c.successor_id OR
            (c.id IS NOT NULL AND (o.relation_type_id<>s.relation_type_id OR NOT o.archived OR
                NOT o.withdrawn OR w.record_id<>o.id OR w.resulting_epoch>o.eligibility_epoch))
        )
    ) OR EXISTS (
        WITH RECURSIVE successors(id) AS (
            SELECT superseded_by_id FROM catalog_relationrecord WHERE id=origin_id
            UNION
            SELECT r.superseded_by_id FROM successors s JOIN catalog_relationrecord r ON r.id=s.id
        )
        SELECT 1 FROM successors WHERE id=origin_id
    ) THEN
        RAISE EXCEPTION 'Invalid identity correction' USING ERRCODE='23514';
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER catalog_record_correction AFTER INSERT OR UPDATE ON catalog_relationrecord
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_validate_correction();
CREATE CONSTRAINT TRIGGER catalog_correction_integrity AFTER INSERT ON catalog_relationidentitycorrection
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_validate_correction();

CREATE FUNCTION catalog_validate_source_gate() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    is_source_gate boolean := TG_TABLE_NAME='catalog_sourcewithdrawalgate';
    blocked_digest text;
BEGIN
    IF is_source_gate THEN blocked_digest=NEW.source_version_digest;
    ELSIF NOT NEW.quarantined THEN RETURN NULL;
    END IF;
    IF EXISTS (
        SELECT 1 FROM catalog_relationrelease l
        JOIN catalog_relationrecord r ON r.id=l.record_id
        JOIN catalog_relationrevision v ON v.id=l.approved_revision_id
        WHERE l.enabled AND r.relation_type_id=NEW.relation_type_id AND v.country=NEW.country
          AND (NOT is_source_gate OR v.source_version_digest=blocked_digest)
    ) THEN
        RAISE EXCEPTION 'Source gate requires disabling affected releases atomically' USING ERRCODE='23514';
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER catalog_source_gate_integrity AFTER INSERT ON catalog_sourcewithdrawalgate
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_validate_source_gate();
CREATE CONSTRAINT TRIGGER catalog_scope_gate_integrity AFTER INSERT OR UPDATE ON catalog_relationscopegate
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_validate_source_gate();

CREATE FUNCTION catalog_validate_selection() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM catalog_entitypresentationselection s
            LEFT JOIN post p ON p.id=s.post_id
            LEFT JOIN classifier_category c ON c.id=s.category_id
            JOIN catalog_catalogentity e ON e.id=s.entity_id
        WHERE ((TG_TABLE_NAME='catalog_entitypresentationselection' AND s.id=NEW.id)
           OR (TG_TABLE_NAME='post' AND s.post_id=NEW.id)
           OR (TG_TABLE_NAME='classifier_category' AND s.category_id=NEW.id))
          AND ((s.post_id IS NOT NULL AND p.entity_id IS DISTINCT FROM s.entity_id)
            OR (s.category_id IS NOT NULL AND (c.entity_id IS DISTINCT FROM s.entity_id OR e.kind<>'crop')))
    ) THEN
        RAISE EXCEPTION 'Presentation selection must match the anchor identity' USING ERRCODE='23514';
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER catalog_selection_integrity AFTER INSERT OR UPDATE ON catalog_entitypresentationselection
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_validate_selection();
CREATE CONSTRAINT TRIGGER catalog_post_anchor_integrity AFTER UPDATE OF entity_id ON post
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_validate_selection();
CREATE CONSTRAINT TRIGGER catalog_category_anchor_integrity AFTER UPDATE OF entity_id ON classifier_category
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_validate_selection();

CREATE FUNCTION catalog_validate_category_entity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.entity_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM catalog_catalogentity WHERE id=NEW.entity_id AND kind='crop'
    ) THEN
        RAISE EXCEPTION 'Category identity must be a crop' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER catalog_category_crop BEFORE INSERT OR UPDATE OF entity_id ON classifier_category
FOR EACH ROW EXECUTE FUNCTION catalog_validate_category_entity();
"""

GUARDS = {
    "catalog_relationtypeversion": ["catalog_schema_immutable"],
    "catalog_relationtype": ["catalog_type_immutable"],
    "catalog_catalogentity": ["catalog_kind_immutable"],
    "catalog_relationauditevent": ["catalog_audit_append_only"],
    "catalog_relationwithdrawal": ["catalog_withdrawal_append_only"],
    "catalog_relationidentitycorrection": ["catalog_correction_append_only", "catalog_correction_integrity"],
    "catalog_sourcewithdrawalgate": ["catalog_source_gate_immutable", "catalog_source_gate_integrity"],
    "catalog_relationscopegate": ["catalog_scope_gate_integrity"],
    "catalog_importreceipt": ["catalog_receipt_immutable"],
    "catalog_relationrecord": ["catalog_record_guard", "catalog_record_release_integrity", "catalog_record_correction"],
    "catalog_relationrevision": ["catalog_revision_guard", "catalog_revision_integrity"],
    "catalog_relationparticipant": ["catalog_participant_guard"],
    "catalog_relationrelease": ["catalog_release_integrity", "catalog_release_lock"],
    "catalog_entitypresentationselection": ["catalog_selection_integrity"],
    "classifier_category": ["catalog_category_crop", "catalog_category_anchor_integrity"],
    "post": ["catalog_post_anchor_integrity"],
}
FUNCTIONS = (
    "catalog_reject_change()",
    "catalog_identity_digest(jsonb)",
    "catalog_guard_record()",
    "catalog_guard_revision()",
    "catalog_guard_participant()",
    "catalog_validate_revision()",
    "catalog_validate_releases()",
    "catalog_lock_release_record()",
    "catalog_validate_correction()",
    "catalog_validate_source_gate()",
    "catalog_validate_selection()",
    "catalog_validate_category_entity()",
)
REMOVE = "\n".join(
    [f"DROP TRIGGER {trigger} ON {table};" for table, triggers in GUARDS.items() for trigger in triggers]
    + [f"DROP FUNCTION {function};" for function in FUNCTIONS]
)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_relationtype_entitypresentationselection_and_more"),
        ("classifier", "0021_category_entity"),
    ]
    operations = [migrations.RunSQL(INSTALL, REMOVE)]
