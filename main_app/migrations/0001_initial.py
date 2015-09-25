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
                ('author', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'announcement',
                'verbose_name': 'announcement',
                'verbose_name_plural': 'announcements',
            },
        ),
        migrations.CreateModel(
            name='Avatar',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('avatar_field', models.ImageField(upload_to=b'/uploads/avatars/', verbose_name='avatar')),
            ],
            options={
                'db_table': 'avatar',
                'verbose_name': 'avatar',
                'verbose_name_plural': 'avatars',
            },
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('category_field', models.CharField(max_length=20, verbose_name='category')),
            ],
            options={
                'db_table': 'category',
                'verbose_name': 'category',
                'verbose_name_plural': 'categories',
            },
        ),
        migrations.CreateModel(
            name='Post',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=150, verbose_name='title')),
                ('date', models.DateTimeField(verbose_name='date')),
                ('text', models.TextField(verbose_name='text')),
                ('post_category', models.ManyToManyField(to='main_app.Category', verbose_name='category')),
            ],
            options={
                'db_table': 'post',
                'verbose_name': 'post',
                'verbose_name_plural': 'posts',
            },
        ),
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
                ('birth_date', models.DateField(verbose_name='birth date', blank=True)),
                ('about', models.TextField(verbose_name='about you', blank=True)),
                ('breed', models.TextField(verbose_name='pigeons breed', blank=True)),
                ('avatar', models.ManyToManyField(to='main_app.Avatar', blank=True)),
                ('location', models.ManyToManyField(to='main_app.Region')),
                ('profile', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_information',
                'verbose_name': 'user information',
                'verbose_name_plural': 'user information',
            },
        ),
    ]
