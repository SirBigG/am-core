# Generated by Django 4.2.7 on 2023-12-26 21:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adverts', '0008_alter_advert_options_advert_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='advert',
            name='slug',
            field=models.SlugField(blank=True, max_length=512, null=True),
        ),
    ]