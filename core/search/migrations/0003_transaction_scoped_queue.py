from django.db import migrations, models

FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION search_mark_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE scope text;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (to_jsonb(OLD) - string_to_array(TG_ARGV[1], ','))
            IS NOT DISTINCT FROM (to_jsonb(NEW) - string_to_array(TG_ARGV[1], ',')) THEN
            RETURN NULL;
        END IF;
    END IF;
    FOREACH scope IN ARRAY string_to_array(TG_ARGV[0], ',') LOOP
        INSERT INTO search_searchdirtyscope (resource_type, transaction_id, revision)
        VALUES (scope, txid_current(), nextval('search_dirty_revision_seq'))
        ON CONFLICT (resource_type, transaction_id) DO UPDATE
        SET revision = EXCLUDED.revision;
    END LOOP;
    RETURN NULL;
END;
$$;
"""


def restore_function(apps, schema_editor):
    from importlib import import_module

    old = import_module("core.search.migrations.0002_source_invalidation").FUNCTION_SQL
    schema_editor.execute(
        old[old.index("CREATE FUNCTION") :].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
    )


class Migration(migrations.Migration):
    dependencies = [("search", "0002_source_invalidation")]
    operations = [
        migrations.DeleteModel(name="SearchDirtyScope"),
        migrations.CreateModel(
            name="SearchDirtyScope",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "resource_type",
                    models.CharField(
                        max_length=16,
                        choices=[
                            ("post", "Матеріали"),
                            ("category", "Категорії"),
                            ("advert", "Оголошення"),
                            ("market", "Агромаркет"),
                            ("company", "Компанії"),
                            ("event", "Події"),
                            ("diary", "Щоденники"),
                            ("registry", "Реєстр сортів"),
                        ],
                    ),
                ),
                ("transaction_id", models.BigIntegerField()),
                ("revision", models.BigIntegerField()),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("resource_type", "transaction_id"), name="search_dirty_transaction_scope"
                    )
                ]
            },
        ),
        migrations.RunSQL(FUNCTION_SQL, migrations.RunSQL.noop),
        # Queue every scope after replacing the old queue; no source mutation
        # or previous invalidation may be lost during this schema transition.
        migrations.RunSQL(
            "INSERT INTO search_searchdirtyscope (resource_type, transaction_id, revision) "
            "SELECT scope, txid_current(), nextval('search_dirty_revision_seq') "
            "FROM unnest(ARRAY['post','category','advert','market','company','event','diary','registry']) AS scope;",
            migrations.RunSQL.noop,
        ),
        migrations.RunPython(migrations.RunPython.noop, restore_function),
    ]
