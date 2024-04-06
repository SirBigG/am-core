# Generated by Django 5.0.3 on 2024-04-02 22:45

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("classifier", "0011_category_absolute_url"),
    ]

    operations = [
        migrations.CreateModel(
            name="Company",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("original_name", models.CharField(blank=True, max_length=255, null=True)),
                ("code", models.IntegerField(blank=True, null=True)),
                (
                    "country",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="classifier.country"
                    ),
                ),
            ],
            options={
                "verbose_name": "Company",
                "verbose_name_plural": "Companies",
            },
        ),
    ]
