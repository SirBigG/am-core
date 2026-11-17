from django.db import migrations

TYPE = "plant_protection_application"
ROLES = {
    "preparation": {"min": 1, "max": 1, "kinds": ["preparation"]},
    "crop": {"min": 1, "max": 1, "kinds": ["crop"]},
    "target": {"min": 0, "max": 1, "kinds": ["disease", "pest", "weed"]},
}
IDENTITY_FIELDS = [
    "country",
    "method",
    "formulation_identity",
    "target_locator",
    "registration_authority",
    "registration_record_key",
    "application_locator",
]


def bootstrap(apps, schema_editor):
    db = schema_editor.connection.alias
    method = apps.get_model("catalog", "ApplicationMethod").objects.using(db)
    for code, label in (
        ("foliar_spray", "Обприскування"),
        ("soil_application", "Ґрунтове внесення"),
        ("seed_treatment", "Обробка насіння"),
    ):
        method.get_or_create(code=code, defaults={"label": label})
    definition, _ = apps.get_model("catalog", "RelationType").objects.using(db).get_or_create(code=TYPE)
    expected = {"roles": ROLES, "identity_roles": ["preparation", "crop", "target"], "identity_fields": IDENTITY_FIELDS}
    version, _ = (
        apps.get_model("catalog", "RelationTypeVersion")
        .objects.using(db)
        .get_or_create(relation_type=definition, version=1, defaults=expected)
    )
    if any(getattr(version, field) != value for field, value in expected.items()):
        raise ValueError("Unexpected immutable application schema")


SQL = r"""
CREATE FUNCTION catalog_guard_application_details() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'Application evidence is immutable' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM catalog_relationrevision WHERE id=NEW.revision_id AND NOT sealed FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Application evidence requires an unsealed revision' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER catalog_application_immutable BEFORE INSERT OR UPDATE OR DELETE
ON catalog_plantprotectionapplicationdetails FOR EACH ROW EXECUTE FUNCTION catalog_guard_application_details();

CREATE FUNCTION catalog_check_application(checked_revision uuid) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v catalog_relationrevision;
    d catalog_plantprotectionapplicationdetails;
    code text;
    target_kind text;
BEGIN
    SELECT * INTO v FROM catalog_relationrevision WHERE id=checked_revision;
    SELECT relation_type_id INTO code FROM catalog_relationrecord WHERE id=v.record_id;
    SELECT * INTO d FROM catalog_plantprotectionapplicationdetails WHERE revision_id=v.id;
    IF code <> 'plant_protection_application' THEN
        IF d.revision_id IS NOT NULL THEN
            RAISE EXCEPTION 'Unexpected application details' USING ERRCODE='23514';
        END IF;
        RETURN;
    END IF;
    IF d.revision_id IS NULL OR v.country !~ '^[A-Z]{2}$'
        OR (v.payload->>'country') IS DISTINCT FROM v.country
        OR v.source_version_digest IS DISTINCT FROM catalog_identity_digest(v.source)
        OR d.source_content_digest !~ '^[a-f0-9]{64}$'
        OR btrim(d.formulation_identity)='' OR btrim(d.registration_authority)=''
        OR btrim(d.registration_record_key)='' OR btrim(d.application_locator)=''
        OR btrim(d.source_reference)='' OR btrim(d.source_document)='' OR btrim(d.source_version)=''
        OR jsonb_typeof(d.formulation_provenance) <> 'object'
        OR jsonb_typeof(d.regulatory_provenance) <> 'object'
        OR d.checked_at > statement_timestamp()
        OR jsonb_build_object('reference',d.source_reference,'document',d.source_document,
            'version',d.source_version,'content_digest',d.source_content_digest) IS DISTINCT FROM v.source
        OR (to_jsonb(d) - ARRAY['revision_id','method_id','source_reference','source_document',
            'source_version','source_content_digest','checked_at','valid_from','valid_until']) IS DISTINCT FROM
           (v.payload - ARRAY['country','method','checked_at','valid_from','valid_until'])
        OR (v.payload->>'method') IS DISTINCT FROM d.method_id
        OR (v.payload->>'checked_at')::timestamptz IS DISTINCT FROM d.checked_at
        OR (v.payload->>'valid_from')::date IS DISTINCT FROM d.valid_from
        OR (v.payload->>'valid_until')::date IS DISTINCT FROM d.valid_until
    THEN
        RAISE EXCEPTION 'Invalid or mismatched application evidence' USING ERRCODE='23514';
    END IF;
    SELECT e.kind INTO target_kind FROM catalog_relationparticipant p
        JOIN catalog_catalogentity e ON e.id=p.entity_id WHERE p.revision_id=v.id AND p.role='target';
    IF (target_kind IS NOT NULL AND (d.target_kind<>target_kind OR d.target_locator<>'' OR d.target_text IS NOT NULL))
        OR (target_kind IS NULL AND (d.target_text IS NULL OR btrim(d.target_text)='' OR
            d.target_locator !~ '^[a-z0-9][a-z0-9_.:-]{0,127}$')) THEN
        RAISE EXCEPTION 'Exact and unresolved application targets must be explicit' USING ERRCODE='23514';
    END IF;
    IF v.state='approved' AND (
        d.formulation_verified IS DISTINCT FROM true OR d.formulation_provenance='{}'::jsonb
        OR NOT EXISTS (SELECT 1 FROM catalog_relationparticipant rp JOIN catalog_catalogentity e ON e.id=rp.entity_id
            WHERE rp.revision_id=v.id AND rp.role='preparation' AND e.provenance->>'formulation_identity'=d.formulation_identity)
        OR d.regulatory_decision<>'confirmed' OR d.regulatory_provenance='{}'::jsonb
        OR d.checked_at IS NULL OR d.valid_from IS NULL OR d.valid_until IS NULL
        OR EXISTS (SELECT 1 FROM catalog_relationwithdrawal w WHERE w.record_id=v.record_id
            AND w.resulting_epoch=v.created_epoch AND d.checked_at < w.occurred_at)
        OR NOT EXISTS (SELECT 1 FROM catalog_applicationmethod m WHERE m.code=d.method_id AND m.active)
        OR NOT EXISTS (SELECT 1 FROM catalog_applicationcountrypolicy p JOIN pg_timezone_names z ON z.name=p.timezone_name
            WHERE p.country=v.country AND p.active)
    ) THEN
        RAISE EXCEPTION 'Application approval requires complete verified evidence' USING ERRCODE='23514';
    END IF;
END $$;
CREATE FUNCTION catalog_validate_application() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME='catalog_relationrevision' THEN PERFORM catalog_check_application(NEW.id);
    ELSE PERFORM catalog_check_application(NEW.revision_id); END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER catalog_application_revision_integrity AFTER INSERT OR UPDATE ON catalog_relationrevision
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_validate_application();
CREATE CONSTRAINT TRIGGER catalog_application_details_integrity AFTER INSERT ON catalog_plantprotectionapplicationdetails
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_validate_application();

CREATE FUNCTION catalog_validate_application_release() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.enabled AND EXISTS (SELECT 1 FROM catalog_relationrecord WHERE id=NEW.record_id
            AND relation_type_id='plant_protection_application') THEN
        PERFORM catalog_check_application(NEW.approved_revision_id);
        IF NOT EXISTS (
            SELECT 1 FROM catalog_relationrevision v
            JOIN catalog_plantprotectionapplicationdetails d ON d.revision_id=v.id
            JOIN catalog_applicationcountrypolicy p ON p.country=v.country
            WHERE v.id=NEW.approved_revision_id AND p.active AND
                (statement_timestamp() AT TIME ZONE p.timezone_name)::date BETWEEN d.valid_from AND d.valid_until
        ) THEN
            RAISE EXCEPTION 'Application release is outside its country validity interval' USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER catalog_application_release_integrity AFTER INSERT OR UPDATE ON catalog_relationrelease
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_validate_application_release();
"""


class Migration(migrations.Migration):
    dependencies = [("catalog", "0009_applicationcountrypolicy_applicationmethod_and_more")]
    operations = [
        migrations.RunPython(bootstrap, migrations.RunPython.noop),
        migrations.RunSQL(
            SQL,
            """DROP TRIGGER catalog_application_release_integrity ON
            catalog_relationrelease; DROP TRIGGER
            catalog_application_revision_integrity ON catalog_relationrevision;
            DROP TRIGGER catalog_application_details_integrity ON
            catalog_plantprotectionapplicationdetails; DROP TRIGGER
            catalog_application_immutable ON
            catalog_plantprotectionapplicationdetails; DROP FUNCTION
            catalog_validate_application_release(); DROP FUNCTION
            catalog_validate_application(); DROP FUNCTION
            catalog_check_application(uuid); DROP FUNCTION
            catalog_guard_application_details();"""

                                                   ,
        ),
    ]
