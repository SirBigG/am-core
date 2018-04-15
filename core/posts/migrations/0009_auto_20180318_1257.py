# Generated by Django 2.0.3 on 2018-03-18 12:57

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('classifier', '0004_auto_20170124_1034'),
        ('posts', '0008_auto_20180318_0948'),
    ]

    operations = [
        migrations.AddField(
            model_name='parsedpost',
            name='is_finished',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='parsedpost',
            name='is_translated',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='parsedpost',
            name='publisher',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='post publisher'),
        ),
        migrations.AddField(
            model_name='parsedpost',
            name='rubric',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='classifier.Category', verbose_name='post category'),
        ),
    ]