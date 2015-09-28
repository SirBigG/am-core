# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0002_auto_20150928_0817'),
    ]

    operations = [
        migrations.CreateModel(
            name='PostPhoto',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('post_photo_field', models.ImageField(upload_to=b'/uploads/post_photos/', verbose_name='post photo')),
            ],
            options={
                'db_table': 'post_photo',
                'verbose_name': 'post photo',
                'verbose_name_plural': 'post photos',
            },
        ),
        migrations.AddField(
            model_name='post',
            name='post_images',
            field=models.ManyToManyField(to='main_app.PostPhoto', verbose_name='post images'),
        ),
    ]
