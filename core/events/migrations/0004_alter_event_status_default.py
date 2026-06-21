from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0003_auto_20190401_1945"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="status",
            field=models.BooleanField(default=True),
        ),
    ]
