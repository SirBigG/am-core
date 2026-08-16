from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("analytics", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="NginxAnalyticsDashboard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "NGINX analytics",
                "verbose_name_plural": "NGINX analytics",
                "permissions": (("view_nginx_analytics", "Can view private NGINX analytics"),),
                "default_permissions": (),
                "managed": False,
            },
        )
    ]
