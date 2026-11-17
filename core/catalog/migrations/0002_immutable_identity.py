from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE FUNCTION catalog_guard_entity_id() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN
                    RAISE EXCEPTION 'CatalogEntity UUID is immutable' USING ERRCODE = '23514';
                END;
                $$;

                CREATE TRIGGER catalog_entity_id_immutable
                AFTER UPDATE ON catalog_catalogentity
                FOR EACH ROW
                WHEN (OLD.id IS DISTINCT FROM NEW.id)
                EXECUTE FUNCTION catalog_guard_entity_id();
            """,
            reverse_sql="""
                DROP TRIGGER catalog_entity_id_immutable ON catalog_catalogentity;
                DROP FUNCTION catalog_guard_entity_id();
            """
               ,
        ),
    ]
