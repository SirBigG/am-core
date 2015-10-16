# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0003_auto_20150928_0820'),
    ]

    operations = [
        migrations.AlterField(
            model_name='announcementphoto',
            name='announcement_photo',
            field=models.ImageField(upload_to=b'uploads/announcement_photos/', verbose_name='announcement photo'),
        ),
        migrations.AlterField(
            model_name='avatar',
            name='avatar_field',
            field=models.ImageField(upload_to=b'uploads/avatars/', verbose_name='avatar'),
        ),
        migrations.RemoveField(
            model_name='post',
            name='post_category',
        ),
        migrations.AddField(
            model_name='post',
            name='post_category',
            field=models.ForeignKey(default=2, verbose_name='category', to='main_app.Category'),
        ),
        migrations.AlterField(
            model_name='postphoto',
            name='post_photo_field',
            field=models.ImageField(upload_to=b'uploads/post_photos/', verbose_name='post photo'),
        ),
    ]
