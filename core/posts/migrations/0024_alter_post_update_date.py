# Generated by Django 4.2.1 on 2023-06-14 09:38

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0023_post_update_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='update_date',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='date of update'),
        ),
    ]
