# Generated by Django 2.0.3 on 2018-03-18 09:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0007_link_parsedmap_parsedpost'),
    ]

    operations = [
        migrations.AlterField(
            model_name='link',
            name='link',
            field=models.URLField(max_length=500, unique=True),
        ),
    ]
