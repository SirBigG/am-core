# Generated by Django 5.0.2 on 2024-03-06 21:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0002_alter_company_options_remove_product_posts_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='slug',
            field=models.SlugField(blank=True, max_length=200, null=True, unique=True),
        ),
    ]
