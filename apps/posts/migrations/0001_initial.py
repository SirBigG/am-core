# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=20, verbose_name='category')),
                ('slug', models.SlugField(unique=True, max_length=20, verbose_name='category slug')),
                ('description', models.TextField(verbose_name='description')),
            ],
            options={
                'db_table': 'category',
                'verbose_name': 'category',
                'verbose_name_plural': 'categories',
            },
        ),
        migrations.CreateModel(
            name='Comments',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('text', models.TextField(verbose_name='comment text')),
                ('publish_date', models.DateTimeField(default=datetime.datetime.now)),
                ('author', models.ForeignKey(verbose_name='comment author', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'post_comments',
                'verbose_name': 'comment',
                'verbose_name_plural': 'comments',
            },
        ),
        migrations.CreateModel(
            name='Post',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=150, verbose_name='title')),
                ('date', models.DateTimeField(default=datetime.datetime.now, verbose_name='date')),
                ('text', models.TextField(verbose_name='text')),
                ('author', models.CharField(max_length=100, verbose_name='post author', blank=True)),
                ('post_category', models.ForeignKey(verbose_name='category', to='posts.Category')),
            ],
            options={
                'db_table': 'post',
                'verbose_name': 'post',
                'verbose_name_plural': 'posts',
            },
        ),
        migrations.CreateModel(
            name='PostPhoto',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('post_photo_field', models.ImageField(upload_to=b'uploads/post_photos/', verbose_name='post photo')),
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
            field=models.ManyToManyField(to='posts.PostPhoto', verbose_name='post images'),
        ),
        migrations.AddField(
            model_name='post',
            name='publisher',
            field=models.ForeignKey(verbose_name='post publisher', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='comments',
            name='post',
            field=models.ForeignKey(to='posts.Post'),
        ),
    ]
