# Generated by Django 3.0.8 on 2020-12-01 19:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classifier', '0009_auto_20200104_1406'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='country',
            options={'ordering': ['value'], 'verbose_name': 'country', 'verbose_name_plural': 'countries'},
        ),
    ]
