from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0018_planner_plannerarea"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlannerPlanting",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mode", models.CharField(choices=[("exact", "Точна кількість"), ("approximate", "Приблизна кількість"), ("rows", "Рядами"), ("area", "За площею"), ("broadcast", "Суцільний посів"), ("unknown", "Без підрахунку")], default="unknown", max_length=24, verbose_name="Спосіб розміщення")),
                ("quantity", models.PositiveIntegerField(blank=True, null=True, verbose_name="Кількість")),
                ("rows", models.PositiveIntegerField(blank=True, null=True, verbose_name="Кількість рядів")),
                ("occupied_area_m2", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))], verbose_name="Зайнята площа, м²")),
                ("notes", models.CharField(blank=True, max_length=255, verbose_name="Примітка")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("area", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="plantings", to="diary.plannerarea", verbose_name="Зона")),
                ("plant", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="planner_placement", to="diary.plant", verbose_name="Рослина або посадка")),
            ],
            options={"ordering": ("created", "id")},
        ),
    ]
