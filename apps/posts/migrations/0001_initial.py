# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
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
                ('post_category', models.ForeignKey(default=2, verbose_name='category', to='posts.Category')),
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
    ]
