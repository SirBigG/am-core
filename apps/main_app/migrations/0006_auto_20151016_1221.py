# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0005_auto_20151012_1101'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userinformation',
            name='location',
        ),
        migrations.RemoveField(
            model_name='userinformation',
            name='profile',
        ),
        migrations.DeleteModel(
            name='UserInformation',
        ),
    ]
