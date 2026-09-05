from django.db import migrations


def seed_rules(apps, schema_editor):
    rule = apps.get_model("companies", "ProductMatchRule")
    database = schema_editor.connection.alias
    # Initial data only. Operators own subsequent changes through the admin.
    ignored = [
        "груша",
        "купити",
        "купить",
        "насіння",
        "поздний",
        "пізній",
        "ранний",
        "ранній",
        "саджанець",
        "саджанца",
        "саджанці",
        "саджанців",
        "саженец",
        "саженцы",
        "семена",
        "середній",
        "сорт",
        "сорта",
        "сорти",
        "сортів",
        "средний",
        "яблоня",
        "яблуня",
        "яблуні",
    ]
    for word in ignored:
        rule.objects.using(database).get_or_create(word=word, defaults={"purpose": "ignore"})
    for word in ("комплект", "набір", "набор", "щеплення", "прививки"):
        rule.objects.using(database).get_or_create(
            word=word, defaults={"purpose": "bundle", "prefix": word == "комплект"}
        )


class Migration(migrations.Migration):
    dependencies = [("companies", "0015_productmatchrule")]
    operations = [migrations.RunPython(seed_rules, migrations.RunPython.noop)]
