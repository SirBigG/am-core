# Generated by Django 3.1.6 on 2021-03-02 20:48

import ckeditor.fields
import datetime
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diary', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='diary',
            name='date',
            field=models.DateField(default=datetime.date.today, verbose_name='Дата'),
        ),
        migrations.AlterField(
            model_name='diary',
            name='description',
            field=ckeditor.fields.RichTextField(verbose_name='Короткий опис'),
        ),
        migrations.AlterField(
            model_name='diaryitem',
            name='description',
            field=ckeditor.fields.RichTextField(verbose_name='Опис'),
        ),
        migrations.AlterField(
            model_name='diaryitem',
            name='diary',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='diary_items', to='diary.diary'),
        ),
    ]