# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2017-10-08 12:07
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0005_post_meta'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='post',
            options={'ordering': ['-publish_date'], 'verbose_name': 'Post', 'verbose_name_plural': 'Posts'},
        ),
    ]
