from django.db import migrations

# Coarse scopes keep dependency invalidation explicit. A category or seller
# update must also refresh every dependent market/search projection.
SOURCES = [
    ("posts", "Post", "post,market", "hits"),
    ("classifier", "Category", "category,post,market,advert", ""),
    ("adverts", "Advert", "advert", "views"),
    ("companies", "Company", "company,market", "parser_map"),
    ("companies", "Product", "market", ""),
    ("events", "Event", "event", ""),
    ("events", "EventType", "event", ""),
    ("diary", "Diary", "diary", ""),
    ("registry", "Variety", "post,market", ""),
    ("registry", "VarietyCategory", "registry", ""),
    ("taggit", "Tag", "post,market", ""),
    ("taggit", "TaggedItem", "post,market", ""),
    ("classifier", "Location", "company,event,advert", ""),
    ("services", "MetaData", "category", ""),
]

FUNCTION_SQL = """
CREATE SEQUENCE search_dirty_revision_seq;
CREATE FUNCTION search_mark_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE scope text;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (to_jsonb(OLD) - string_to_array(TG_ARGV[1], ','))
            IS NOT DISTINCT FROM (to_jsonb(NEW) - string_to_array(TG_ARGV[1], ',')) THEN
            RETURN NULL;
        END IF;
    END IF;
    FOREACH scope IN ARRAY string_to_array(TG_ARGV[0], ',') LOOP
        INSERT INTO search_searchdirtyscope (resource_type, revision)
        VALUES (scope, nextval('search_dirty_revision_seq'))
        ON CONFLICT (resource_type) DO UPDATE
        SET revision = GREATEST(search_searchdirtyscope.revision, EXCLUDED.revision);
    END LOOP;
    RETURN NULL;
END;
$$;
"""


def install(apps, schema_editor):
    schema_editor.execute(FUNCTION_SQL)
    quote = schema_editor.quote_name
    for app, model, scopes, ignored in SOURCES:
        table = quote(apps.get_model(app, model)._meta.db_table)
        # Literals are fixed migration constants, never user input.
        arguments = f"'{scopes}', '{ignored}'"
        schema_editor.execute(
            f"CREATE TRIGGER search_dirty_write AFTER INSERT OR DELETE OR TRUNCATE ON {table} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION search_mark_dirty({arguments})"
        )
        schema_editor.execute(
            f"CREATE TRIGGER search_dirty_update AFTER UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION search_mark_dirty({arguments})"
        )


def uninstall(apps, schema_editor):
    for app, model, _, _ in SOURCES:
        table = schema_editor.quote_name(apps.get_model(app, model)._meta.db_table)
        schema_editor.execute(f"DROP TRIGGER IF EXISTS search_dirty_write ON {table}")
        schema_editor.execute(f"DROP TRIGGER IF EXISTS search_dirty_update ON {table}")
    schema_editor.execute("DROP FUNCTION search_mark_dirty(); DROP SEQUENCE search_dirty_revision_seq;")


class Migration(migrations.Migration):
    dependencies = [
        ("search", "0001_initial"),
        ("posts", "0035_guide_hub_foundation"),
        ("classifier", "0018_categoryhub_market_category"),
        ("adverts", "0012_advertimage_optional_advert_image"),
        ("companies", "0018_marketpage"),
        ("events", "0004_alter_event_status_default"),
        ("diary", "0017_diaryitem_harvest_fields"),
        ("registry", "0006_registryimportjob"),
        ("taggit", "0006_rename_taggeditem_content_type_object_id_taggit_tagg_content_8fc721_idx"),
    ]
    operations = [migrations.RunPython(install, uninstall)]
