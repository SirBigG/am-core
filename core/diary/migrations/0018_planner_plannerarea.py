from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0017_diaryitem_harvest_fields"),
        ("pro_auth", "0006_auto_20180416_1655"),
    ]

    operations = [
        migrations.CreateModel(
            name="Planner",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(default="Моя ділянка", max_length=255, verbose_name="Назва")),
                ("width_m", models.DecimalField(decimal_places=2, default="20.00", max_digits=8, validators=[django.core.validators.MinValueValidator(Decimal("1.00"))], verbose_name="Ширина, м")),
                ("height_m", models.DecimalField(decimal_places=2, default="12.00", max_digits=8, validators=[django.core.validators.MinValueValidator(Decimal("1.00"))], verbose_name="Довжина, м")),
                ("grid_step_m", models.DecimalField(decimal_places=2, default="0.50", max_digits=4, validators=[django.core.validators.MinValueValidator(Decimal("0.10"))], verbose_name="Крок сітки, м")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="planners", to="pro_auth.user", verbose_name="Користувач")),
            ],
            options={"ordering": ("-updated", "-id")},
        ),
        migrations.CreateModel(
            name="PlannerArea",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255, verbose_name="Назва")),
                ("area_type", models.CharField(choices=[("bed", "Грядка"), ("greenhouse", "Теплиця"), ("field", "Поле"), ("garden", "Город"), ("other", "Інша зона")], default="bed", max_length=24, verbose_name="Тип зони")),
                ("x_m", models.DecimalField(decimal_places=2, default="0.00", max_digits=8, verbose_name="X, м")),
                ("y_m", models.DecimalField(decimal_places=2, default="0.00", max_digits=8, verbose_name="Y, м")),
                ("width_m", models.DecimalField(decimal_places=2, default="4.00", max_digits=8, validators=[django.core.validators.MinValueValidator(Decimal("0.50"))], verbose_name="Ширина, м")),
                ("height_m", models.DecimalField(decimal_places=2, default="1.20", max_digits=8, validators=[django.core.validators.MinValueValidator(Decimal("0.50"))], verbose_name="Довжина, м")),
                ("color", models.CharField(default="#69a85f", max_length=16, verbose_name="Колір")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("diary", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="planner_area", to="diary.diary", verbose_name="Щоденник")),
                ("planner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="areas", to="diary.planner", verbose_name="Планер")),
            ],
            options={"ordering": ("created", "id")},
        ),
    ]
