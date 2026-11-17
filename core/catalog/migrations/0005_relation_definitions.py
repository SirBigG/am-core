from django.db import migrations

KINDS = ["crop", "cultivar", "disease", "pest", "weed", "preparation"]
DEFINITIONS = {
    "related_to": ({"member": {"min": 2, "max": 2, "kinds": KINDS}}, ["member"]),
    "cultivar_of": (
        {"cultivar": {"min": 1, "max": 1, "kinds": ["cultivar"]}, "crop": {"min": 1, "max": 1, "kinds": ["crop"]}},
        ["cultivar"],
    ),
}


def bootstrap(apps, schema_editor):
    db = schema_editor.connection.alias
    types = apps.get_model("catalog", "RelationType").objects.using(db)
    versions = apps.get_model("catalog", "RelationTypeVersion").objects.using(db)
    for code, (roles, identity_roles) in DEFINITIONS.items():
        definition, _ = types.get_or_create(code=code)
        expected = {"roles": roles, "identity_roles": identity_roles, "identity_fields": []}
        version, _ = versions.get_or_create(relation_type=definition, version=1, defaults=expected)
        if any(getattr(version, field) != value for field, value in expected.items()):
            raise ValueError(f"Unexpected immutable schema for {code}/1")


class Migration(migrations.Migration):
    dependencies = [("catalog", "0004_relation_guards")]
    operations = [migrations.RunPython(bootstrap, migrations.RunPython.noop)]
