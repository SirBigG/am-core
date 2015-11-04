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
            name='Region',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('region_field', models.CharField(max_length=20, verbose_name='region')),
            ],
            options={
                'db_table': 'region',
                'verbose_name': 'region',
                'verbose_name_plural': 'regions',
            },
        ),
        migrations.CreateModel(
            name='UserInformation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('avatar', models.ImageField(upload_to=b'uploads/avatars/', verbose_name='avatar', blank=True)),
                ('phone', models.IntegerField(unique=True, verbose_name='phone', blank=True)),
                ('birth_date', models.DateField(verbose_name='birth date', blank=True)),
                ('about', models.TextField(verbose_name='about you', blank=True)),
                ('breed', models.TextField(verbose_name='pigeons breed', blank=True)),
                ('location', models.ForeignKey(default=2, verbose_name='location', to='uagent.Region')),
                ('profile', models.OneToOneField(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_information',
                'verbose_name': 'user information',
                'verbose_name_plural': 'user information',
            },
        ),
    ]
