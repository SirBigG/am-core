# Generated by Django 4.2.5 on 2023-09-04 15:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adverts', '0006_alter_advert_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='advert',
            name='updated',
            field=models.DateTimeField(auto_now=True),
        ),
    ]