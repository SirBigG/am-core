# Generated by Django 2.0.3 on 2018-11-04 21:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('classifier', '0004_auto_20170124_1034'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.CharField(max_length=255, unique=True, verbose_name='transliteration value')),
                ('title', models.CharField(max_length=255, verbose_name='tag title')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classifier.Category', verbose_name='tag category')),
            ],
            options={
                'verbose_name': 'tag',
                'verbose_name_plural': 'tags',
                'db_table': 'tags',
            },
        ),
        migrations.CreateModel(
            name='Type',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.CharField(max_length=255, unique=True, verbose_name='transliteration value')),
                ('title', models.CharField(max_length=255, verbose_name='type title')),
            ],
            options={
                'verbose_name': 'tag type',
                'verbose_name_plural': 'tag types',
                'db_table': 'tag_types',
            },
        ),
        migrations.AddField(
            model_name='tag',
            name='type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classifier.Type', verbose_name='tag type'),
        ),
    ]
