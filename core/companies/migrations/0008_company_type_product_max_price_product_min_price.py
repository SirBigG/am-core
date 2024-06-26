# Generated by Django 5.0.3 on 2024-05-05 11:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0007_link"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="type",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "Магазин"), (2, "Сервіс"), (3, "Супермаркет"), (4, "Ринок")], default=1
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="max_price",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="min_price",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
