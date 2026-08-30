from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0012_parser_ingestion_hardening"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="link",
            options={
                "permissions": [
                    ("use_parser_worker_api", "Can use parser worker API"),
                    ("run_parser_source_on_demand", "Can run parser sources on demand"),
                ]
            },
        ),
    ]
