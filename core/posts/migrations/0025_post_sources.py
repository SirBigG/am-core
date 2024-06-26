# Generated by Django 5.0.3 on 2024-04-21 15:49

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("posts", "0024_alter_post_update_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="sources",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=250),
                blank=True,
                null=True,
                size=None,
                verbose_name="post sources",
            ),
        ),
    ]
