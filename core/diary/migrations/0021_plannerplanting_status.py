from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0020_plannerplanting_geometry"),
    ]

    operations = [
        migrations.AddField(
            model_name="plannerplanting",
            name="status",
            field=models.CharField(choices=[("planned", "Заплановано"), ("planted", "Посаджено"), ("growing", "Росте"), ("harvest", "Збір урожаю"), ("completed", "Завершено")], default="planned", max_length=16, verbose_name="Статус"),
        ),
    ]
