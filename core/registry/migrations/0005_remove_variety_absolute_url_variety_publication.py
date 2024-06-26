# Generated by Django 5.0.3 on 2024-04-05 22:55

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("posts", "0024_alter_post_update_date"),
        ("registry", "0004_variety_absolute_url"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="variety",
            name="absolute_url",
        ),
        migrations.AddField(
            model_name="variety",
            name="publication",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="posts.post"
            ),
        ),
    ]
