from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0021_plannerplanting_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlannerTask",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255, verbose_name="Завдання")),
                ("due_date", models.DateField(blank=True, null=True, verbose_name="Запланована дата")),
                ("is_completed", models.BooleanField(default=False, verbose_name="Виконано")),
                ("completed_at", models.DateTimeField(blank=True, null=True, verbose_name="Виконано о")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "area",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tasks",
                        to="diary.plannerarea",
                        verbose_name="Зона",
                    ),
                ),
                (
                    "planner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="diary.planner",
                        verbose_name="Планер",
                    ),
                ),
            ],
            options={"ordering": ("is_completed", "due_date", "created", "id")},
        ),
    ]
