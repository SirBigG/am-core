from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0015_diaryitem_apply_to_all"),
    ]

    operations = [
        migrations.AlterField(
            model_name="diaryitem",
            name="action_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("watering", "💧 Підлив"),
                    ("fertilizer", "🌿 Добриво"),
                    ("photo", "📷 Фото"),
                    ("note", "✏️ Нотатка"),
                    ("planted", "🌱 Посаджено"),
                    ("transplanted", "🪴 Пересаджено"),
                    ("disease", "🤒 Хвороба"),
                    ("pest", "🐛 Шкідник"),
                    ("pruning", "✂️ Обрізка"),
                    ("harvest", "🧺 Збір урожаю"),
                    ("finished", "🏁 Завершити рослину"),
                ],
                default="",
                max_length=32,
                verbose_name="Оберіть швидку дію",
            ),
        ),
    ]
