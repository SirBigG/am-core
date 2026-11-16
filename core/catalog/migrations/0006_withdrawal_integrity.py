import django.db.models.deletion
from django.db import migrations, models

INSTALL = """
CREATE FUNCTION catalog_lock_eligibility_type(type_code varchar) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    -- Match the service lock order. A real write to the fence also makes a stale
    -- REPEATABLE READ snapshot fail instead of validating against old gate data.
    PERFORM 1 FROM catalog_relationtype WHERE code=type_code FOR UPDATE;
    INSERT INTO catalog_eligibility_fence (relation_type_id, generation) VALUES (type_code, 1)
    ON CONFLICT (relation_type_id) DO UPDATE SET generation=catalog_eligibility_fence.generation+1;
END $$;

CREATE FUNCTION catalog_lock_eligibility() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE type_code varchar(64);
BEGIN
    IF TG_TABLE_NAME IN ('catalog_relationrelease', 'catalog_relationrevision') THEN
        SELECT relation_type_id INTO STRICT type_code FROM catalog_relationrecord WHERE id=NEW.record_id;
    ELSE
        type_code=NEW.relation_type_id;
    END IF;
    PERFORM catalog_lock_eligibility_type(type_code);
    RETURN NEW;
END $$;

CREATE TRIGGER catalog_00_release_eligibility BEFORE INSERT OR UPDATE ON catalog_relationrelease
FOR EACH ROW EXECUTE FUNCTION catalog_lock_eligibility();
CREATE TRIGGER catalog_00_revision_eligibility BEFORE INSERT OR UPDATE ON catalog_relationrevision
FOR EACH ROW EXECUTE FUNCTION catalog_lock_eligibility();
CREATE TRIGGER catalog_00_source_eligibility BEFORE INSERT ON catalog_sourcewithdrawalgate
FOR EACH ROW EXECUTE FUNCTION catalog_lock_eligibility();
CREATE TRIGGER catalog_00_scope_eligibility BEFORE INSERT OR UPDATE ON catalog_relationscopegate
FOR EACH ROW EXECUTE FUNCTION catalog_lock_eligibility();

CREATE FUNCTION catalog_guard_scope_gate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Scope gate must be retained' USING ERRCODE='23514';
    END IF;
    IF ROW(OLD.id, OLD.relation_type_id, OLD.country) IS DISTINCT FROM
       ROW(NEW.id, NEW.relation_type_id, NEW.country) OR NEW.lock_version <= OLD.lock_version THEN
        RAISE EXCEPTION 'Scope gate identity is immutable and its version must advance' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER catalog_scope_change_guard BEFORE UPDATE OR DELETE ON catalog_relationscopegate
FOR EACH ROW EXECUTE FUNCTION catalog_guard_scope_gate();

CREATE FUNCTION catalog_guard_withdrawal_transition() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NEW.withdrawn OR NEW.eligibility_epoch<>0 THEN
            RAISE EXCEPTION 'New relation must start at the initial eligibility epoch' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    END IF;
    IF ROW(NEW.withdrawn, NEW.eligibility_epoch) IS NOT DISTINCT FROM
       ROW(OLD.withdrawn, OLD.eligibility_epoch) THEN
        RETURN NEW;
    END IF;
    IF NEW.lock_version<>OLD.lock_version+1 OR (
        NEW.withdrawn AND NEW.eligibility_epoch<>OLD.eligibility_epoch+1
    ) OR (
        NOT NEW.withdrawn AND (NEW.eligibility_epoch<>OLD.eligibility_epoch OR NOT OLD.withdrawn)
    ) THEN
        RAISE EXCEPTION 'Withdrawal transition must advance version and retain epoch semantics' USING ERRCODE='23514';
    END IF;
    PERFORM catalog_lock_eligibility_type(NEW.relation_type_id);
    IF EXISTS (SELECT 1 FROM catalog_relationrelease WHERE record_id=OLD.id AND enabled) THEN
        RAISE EXCEPTION 'Withdrawal or reinstatement requires disabled releases' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER catalog_withdrawal_transition BEFORE INSERT OR UPDATE ON catalog_relationrecord
FOR EACH ROW EXECUTE FUNCTION catalog_guard_withdrawal_transition();

CREATE FUNCTION catalog_validate_withdrawal_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.withdrawn THEN
        IF NOT EXISTS (
            SELECT 1 FROM catalog_relationwithdrawal w
            JOIN catalog_relationauditevent a ON a.record_id=w.record_id AND a.actor_id=w.actor_id
                AND a.action='withdraw' AND a.base_version=OLD.lock_version
                AND a.result->>'withdrawal'=w.id::text
            WHERE w.record_id=NEW.id AND w.resulting_epoch=NEW.eligibility_epoch
                AND btrim(w.reason)<>'' AND w.evidence NOT IN ('null'::jsonb, '{}'::jsonb, '[]'::jsonb, '""'::jsonb)
        ) THEN
            RAISE EXCEPTION 'Withdrawal requires matching history and audit' USING ERRCODE='23514';
        END IF;
    ELSIF NOT EXISTS (
        SELECT 1 FROM catalog_relationwithdrawal w
        JOIN catalog_relationauditevent a ON a.record_id=w.record_id AND a.action='reinstate'
            AND a.base_version=OLD.lock_version AND a.result->>'withdrawal'=w.id::text
        JOIN catalog_relationrevision v ON v.id=a.revision_id AND v.record_id=w.record_id
        WHERE w.record_id=NEW.id AND w.resulting_epoch=NEW.eligibility_epoch
            AND v.sealed AND v.state='approved' AND v.created_epoch=NEW.eligibility_epoch
            AND v.approval_epoch=NEW.eligibility_epoch
            AND a.result->'evidence' NOT IN ('null'::jsonb, '{}'::jsonb, '[]'::jsonb, '""'::jsonb)
            AND NOT EXISTS (
                SELECT 1 FROM catalog_sourcewithdrawalgate g WHERE g.relation_type_id=NEW.relation_type_id
                    AND g.country=v.country AND g.source_version_digest=v.source_version_digest
            )
            AND NOT EXISTS (
                SELECT 1 FROM catalog_relationscopegate g WHERE g.relation_type_id=NEW.relation_type_id
                    AND g.country=v.country AND g.quarantined
            )
    ) THEN
        RAISE EXCEPTION 'Reinstatement requires new approved revision, withdrawal reference and audit'
            USING ERRCODE='23514';
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER catalog_withdrawal_history AFTER UPDATE ON catalog_relationrecord
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
WHEN (ROW(OLD.withdrawn, OLD.eligibility_epoch) IS DISTINCT FROM ROW(NEW.withdrawn, NEW.eligibility_epoch))
EXECUTE FUNCTION catalog_validate_withdrawal_history();

CREATE FUNCTION catalog_guard_withdrawal_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_record catalog_relationrecord;
BEGIN
    SELECT * INTO STRICT current_record FROM catalog_relationrecord WHERE id=NEW.record_id FOR UPDATE;
    IF TG_TABLE_NAME='catalog_relationwithdrawal' THEN
        IF NOT current_record.withdrawn OR NEW.resulting_epoch<>current_record.eligibility_epoch THEN
            RAISE EXCEPTION 'Withdrawal evidence must match an active withdrawal' USING ERRCODE='23514';
        END IF;
    ELSIF NEW.base_version IS DISTINCT FROM current_record.lock_version-1
       OR current_record.withdrawn IS DISTINCT FROM (NEW.action='withdraw') THEN
        RAISE EXCEPTION 'Audit must refer to the current withdrawal transition' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER catalog_withdrawal_evidence BEFORE INSERT ON catalog_relationwithdrawal
FOR EACH ROW EXECUTE FUNCTION catalog_guard_withdrawal_evidence();
CREATE TRIGGER catalog_withdrawal_audit BEFORE INSERT ON catalog_relationauditevent
FOR EACH ROW WHEN (NEW.action IN ('withdraw', 'reinstate')) EXECUTE FUNCTION catalog_guard_withdrawal_evidence();
"""

REMOVE = """
DROP TRIGGER catalog_withdrawal_audit ON catalog_relationauditevent;
DROP TRIGGER catalog_withdrawal_evidence ON catalog_relationwithdrawal;
DROP FUNCTION catalog_guard_withdrawal_evidence();
DROP TRIGGER catalog_withdrawal_history ON catalog_relationrecord;
DROP FUNCTION catalog_validate_withdrawal_history();
DROP TRIGGER catalog_withdrawal_transition ON catalog_relationrecord;
DROP FUNCTION catalog_guard_withdrawal_transition();
DROP TRIGGER catalog_scope_change_guard ON catalog_relationscopegate;
DROP FUNCTION catalog_guard_scope_gate();
DROP TRIGGER catalog_00_scope_eligibility ON catalog_relationscopegate;
DROP TRIGGER catalog_00_source_eligibility ON catalog_sourcewithdrawalgate;
DROP TRIGGER catalog_00_revision_eligibility ON catalog_relationrevision;
DROP TRIGGER catalog_00_release_eligibility ON catalog_relationrelease;
DROP FUNCTION catalog_lock_eligibility();
DROP FUNCTION catalog_lock_eligibility_type(varchar);
"""


class Migration(migrations.Migration):
    dependencies = [("catalog", "0005_relation_definitions")]
    operations = [
        migrations.CreateModel(
            name="RelationEligibilityFence",
            fields=[
                (
                    "relation_type",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        primary_key=True,
                        serialize=False,
                        to="catalog.relationtype",
                    ),
                ),
                ("generation", models.PositiveBigIntegerField(default=1)),
            ],
            options={"db_table": "catalog_eligibility_fence", "default_permissions": ()},
        ),
        migrations.RunSQL(INSTALL, REMOVE),
    ]
