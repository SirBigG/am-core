# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnnouncementPhoto',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('announcement_photo', models.ImageField(upload_to=b'/uploads/announcement_photos/', verbose_name='announcement photo')),
            ],
            options={
                'db_table': 'announcement_photo',
                'verbose_name': 'announcement photo',
                'verbose_name_plural': 'announcement photos',
            },
        ),
        migrations.AddField(
            model_name='announcement',
            name='ann_photo',
            field=models.ManyToManyField(to='main_app.AnnouncementPhoto', verbose_name='announcements photo'),
        ),
    ]
