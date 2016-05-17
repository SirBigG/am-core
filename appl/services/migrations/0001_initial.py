# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-04-27 15:12
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Feedback',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='feedback topic')),
                ('email', models.EmailField(max_length=254, verbose_name='feedback email')),
                ('text', models.TextField(verbose_name='feedback body')),
            ],
            options={
                'db_table': 'feedback',
                'verbose_name': 'Feedback',
                'verbose_name_plural': 'Feedbacks',
            },
        ),
    ]