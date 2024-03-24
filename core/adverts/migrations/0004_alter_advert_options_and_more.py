# Generated by Django 4.2.3 on 2023-07-07 22:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adverts', '0003_auto_20201201_2024'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='advert',
            options={'ordering': ['created'], 'verbose_name': 'advert', 'verbose_name_plural': 'adverts'},
        ),
        migrations.AddIndex(
            model_name='advert',
            index=models.Index(fields=['created'], name='adverts_adv_created_b6783f_idx'),
        ),
    ]