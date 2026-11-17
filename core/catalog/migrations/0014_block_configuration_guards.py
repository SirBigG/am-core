from django.db import migrations

SQL = r"""
CREATE FUNCTION catalog_guard_block_configuration() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Block history must be retained' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' AND (
   ROW(NEW.id,NEW.hub_id,NEW.site_id,NEW.content_locale,NEW.owner_id,NEW.created_by_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.hub_id,OLD.site_id,OLD.content_locale,OLD.owner_id,OLD.created_by_id,OLD.created_at)
   OR NEW.lock_version<=OLD.lock_version)
 THEN RAISE EXCEPTION 'Immutable block scope or stale version' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' AND NOT EXISTS (
   SELECT 1 FROM classifier_categoryhub h JOIN classifier_category c ON c.id=h.category_id
   JOIN catalog_catalogentity e ON e.id=c.entity_id
   WHERE h.id=NEW.hub_id AND e.id=NEW.owner_id AND e.kind='crop'
     AND (h.site_id IS NULL OR h.site_id=NEW.site_id) AND (h.locale='' OR h.locale=NEW.content_locale))
 THEN RAISE EXCEPTION 'Block owner/site/locale mismatch' USING ERRCODE='23514'; END IF;
 IF NEW.active_revision_id IS NOT NULL AND NOT EXISTS (
   SELECT 1 FROM catalog_blockconfigurationrevision v WHERE v.id=NEW.active_revision_id AND v.configuration_id=NEW.id)
 THEN RAISE EXCEPTION 'Foreign active configuration revision' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER catalog_block_configuration_guard BEFORE INSERT OR UPDATE OR DELETE ON catalog_blockconfiguration
FOR EACH ROW EXECUTE FUNCTION catalog_guard_block_configuration();

CREATE FUNCTION catalog_guard_block_revision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE b jsonb; i jsonb;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Configuration revisions are immutable' USING ERRCODE='23514'; END IF;
 IF jsonb_typeof(NEW.blocks)<>'array' OR jsonb_array_length(NEW.blocks) NOT BETWEEN 1 AND 3 OR NEW.number<1
 THEN RAISE EXCEPTION 'Bounded block array required' USING ERRCODE='23514'; END IF;
 FOR b IN SELECT value FROM jsonb_array_elements(NEW.blocks) LOOP
  IF jsonb_typeof(b)<>'object' OR EXISTS (SELECT 1 FROM jsonb_each(b) WHERE value='null'::jsonb) OR (SELECT count(*) FROM jsonb_object_keys(b))<>15
    OR b - ARRAY['version','slot','title','type','context_role','result_role','filters','conditions','country_policy',
                 'sort','page_size','empty','presentation','manual_replacement','manual_ids'] <> '{}'::jsonb
    OR b->'version'<>'1'::jsonb OR jsonb_typeof(b->'title')<>'string' OR length(b->>'title') NOT BETWEEN 1 AND 200
    OR b->>'slot' NOT IN ('crop.related_preparations','crop.related_problems','crop.related_catalog')
    OR b->>'type' NOT IN ('plant_protection_application','cultivar_of','related_to')
    OR b->>'country_policy'<>'resolved_market' OR b->>'sort'<>'canonical_title_uuid'
    OR b->>'empty'<>'hide' OR b->>'presentation' NOT IN ('catalog_cards','catalog_list')
    OR b->>'manual_replacement' NOT IN ('none','guide_placements')
    OR jsonb_typeof(b->'filters')<>'array' OR jsonb_typeof(b->'conditions')<>'object'
    OR jsonb_typeof(b->'manual_ids')<>'array' OR jsonb_array_length(b->'manual_ids')>50
    OR jsonb_typeof(b->'page_size')<>'number' OR (b->>'page_size') !~ '^[0-9]+$'
    OR (b->>'page_size')::numeric NOT BETWEEN 1 AND 20
  THEN RAISE EXCEPTION 'Invalid declarative block fields' USING ERRCODE='23514'; END IF;
  FOR i IN SELECT value FROM jsonb_array_elements(b->'manual_ids') LOOP
    IF jsonb_typeof(i)<>'number' OR i::text !~ '^[1-9][0-9]*$' THEN
      RAISE EXCEPTION 'Explicit placement IDs required' USING ERRCODE='23514'; END IF;
  END LOOP;
 END LOOP;
 IF (SELECT count(DISTINCT value->>'slot') FROM jsonb_array_elements(NEW.blocks))<>jsonb_array_length(NEW.blocks)
 THEN RAISE EXCEPTION 'Duplicate block slot' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER catalog_block_revision_guard BEFORE INSERT OR UPDATE OR DELETE ON catalog_blockconfigurationrevision
FOR EACH ROW EXECUTE FUNCTION catalog_guard_block_revision();

CREATE FUNCTION catalog_check_block_manual() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v catalog_blockconfigurationrevision; expected bigint;
BEGIN
 IF TG_TABLE_NAME='catalog_blockconfigurationrevision' THEN v:=NEW;
 ELSE SELECT * INTO v FROM catalog_blockconfigurationrevision WHERE id=NEW.revision_id; END IF;
 SELECT COALESCE(sum(jsonb_array_length(b->'manual_ids')),0) INTO expected FROM jsonb_array_elements(v.blocks) b;
 IF expected>50 OR expected<>(SELECT count(*) FROM catalog_blockmanualplacement WHERE revision_id=v.id)
   OR EXISTS (SELECT 1 FROM catalog_blockmanualplacement m WHERE m.revision_id=v.id AND NOT EXISTS (
     SELECT 1 FROM jsonb_array_elements(v.blocks) b WHERE b->>'slot'=m.slot AND b->'manual_ids' @> to_jsonb(ARRAY[m.placement_id])))
 THEN RAISE EXCEPTION 'Manual placement manifest mismatch' USING ERRCODE='23514'; END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER catalog_block_manual_revision AFTER INSERT ON catalog_blockconfigurationrevision
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_check_block_manual();
CREATE CONSTRAINT TRIGGER catalog_block_manual_binding AFTER INSERT ON catalog_blockmanualplacement
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_check_block_manual();
CREATE TRIGGER catalog_block_manual_immutable BEFORE UPDATE OR DELETE ON catalog_blockmanualplacement
FOR EACH ROW EXECUTE FUNCTION catalog_reject_change();
CREATE TRIGGER catalog_block_audit_immutable BEFORE UPDATE OR DELETE ON catalog_blockconfigurationaudit
FOR EACH ROW EXECUTE FUNCTION catalog_reject_change();
"""
REVERSE = """
DROP TRIGGER catalog_block_audit_immutable ON catalog_blockconfigurationaudit;
DROP TRIGGER catalog_block_manual_immutable ON catalog_blockmanualplacement;
DROP TRIGGER catalog_block_manual_binding ON catalog_blockmanualplacement;
DROP TRIGGER catalog_block_manual_revision ON catalog_blockconfigurationrevision;
DROP FUNCTION catalog_check_block_manual();
DROP TRIGGER catalog_block_revision_guard ON catalog_blockconfigurationrevision;
DROP FUNCTION catalog_guard_block_revision();
DROP TRIGGER catalog_block_configuration_guard ON catalog_blockconfiguration;
DROP FUNCTION catalog_guard_block_configuration();
"""


class Migration(migrations.Migration):
    dependencies = [("catalog", "0013_blockconfiguration_blockconfigurationrevision_and_more")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
