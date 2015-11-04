# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Announcement',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=150, verbose_name='announcement title')),
                ('date', models.DateTimeField(verbose_name='date')),
                ('text', models.TextField(verbose_name='announcement text')),
            ],
            options={
                'db_table': 'announcement',
                'verbose_name': 'announcement',
                'verbose_name_plural': 'announcements',
            },
        ),
        migrations.CreateModel(
            name='AnnouncementPhoto',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('announcement_photo', models.ImageField(upload_to=b'uploads/announcement_photos/', verbose_name='announcement photo')),
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
        migrations.AddField(
            model_name='announcement',
            name='author',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
        ),
    ]
