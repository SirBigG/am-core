# Generated manually because local Docker was unavailable.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0016_alter_diaryitem_action_type_transplanted"),
    ]

    operations = [
        migrations.AddField(
            model_name="diaryitem",
            name="harvest_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=8,
                null=True,
                verbose_name="Кількість урожаю",
            ),
        ),
        migrations.AddField(
            model_name="diaryitem",
            name="harvest_unit",
            field=models.CharField(
                blank=True,
                choices=[("kg", "кг"), ("g", "г"), ("pcs", "шт"), ("bunch", "пучок")],
                default="",
                max_length=16,
                verbose_name="Одиниця урожаю",
            ),
        ),
    ]
