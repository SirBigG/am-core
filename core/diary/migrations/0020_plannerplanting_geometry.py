from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0019_plannerplanting"),
    ]

    operations = [
        migrations.AddField(
            model_name="plannerplanting",
            name="x_pct",
            field=models.DecimalField(decimal_places=2, default="5.00", max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal("0")), django.core.validators.MaxValueValidator(Decimal("100"))], verbose_name="X, %"),
        ),
        migrations.AddField(
            model_name="plannerplanting",
            name="y_pct",
            field=models.DecimalField(decimal_places=2, default="5.00", max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal("0")), django.core.validators.MaxValueValidator(Decimal("100"))], verbose_name="Y, %"),
        ),
        migrations.AddField(
            model_name="plannerplanting",
            name="width_pct",
            field=models.DecimalField(decimal_places=2, default="35.00", max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal("5")), django.core.validators.MaxValueValidator(Decimal("100"))], verbose_name="Ширина, %"),
        ),
        migrations.AddField(
            model_name="plannerplanting",
            name="height_pct",
            field=models.DecimalField(decimal_places=2, default="35.00", max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal("5")), django.core.validators.MaxValueValidator(Decimal("100"))], verbose_name="Висота, %"),
        ),
    ]
