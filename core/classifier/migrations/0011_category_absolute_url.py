# Generated by Django 4.2.3 on 2023-07-07 22:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classifier', '0010_auto_20201201_1933'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='absolute_url',
            field=models.CharField(blank=True, max_length=1000, null=True, verbose_name='absolute url'),
        ),
    ]
