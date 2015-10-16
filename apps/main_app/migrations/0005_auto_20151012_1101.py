# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0004_auto_20151001_1256'),
    ]

    operations = [
        migrations.AddField(
            model_name='userinformation',
            name='phone',
            field=models.IntegerField(default=1, unique=True, verbose_name='phone', blank=True),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name='userinformation',
            name='avatar',
        ),
        migrations.AddField(
            model_name='userinformation',
            name='avatar',
            field=models.ImageField(default=1, upload_to=b'uploads/avatars/', verbose_name='avatar'),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name='userinformation',
            name='location',
        ),
        migrations.AddField(
            model_name='userinformation',
            name='location',
            field=models.ForeignKey(default=2, verbose_name='location', to='main_app.Region'),
        ),
        migrations.AlterField(
            model_name='userinformation',
            name='profile',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, unique=True),
        ),
        migrations.DeleteModel(
            name='Avatar',
        ),
    ]
