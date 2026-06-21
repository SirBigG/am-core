from importlib import import_module

from django.db import migrations

PAGES = import_module("core.services.migrations.0013_seed_legal_flatpages").PAGES


def refresh_legal_flatpage_content(apps, schema_editor):
    FlatPage = apps.get_model("flatpages", "FlatPage")
    Site = apps.get_model("sites", "Site")

    sites = list(Site.objects.all())
    if not sites:
        sites = [Site.objects.create(domain="agromega.in.ua", name="AgroMega")]

    for page_data in PAGES:
        page, _created = FlatPage.objects.update_or_create(
            url=page_data["url"],
            defaults={
                "title": page_data["title"],
                "content": page_data["content"],
                "enable_comments": False,
                "registration_required": False,
                "template_name": "",
            },
        )
        page.sites.add(*sites)


def noop_reverse(apps, schema_editor):
    # Avoid restoring older legal text during rollback because it may have been edited in admin.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("services", "0013_seed_legal_flatpages"),
    ]

    operations = [
        migrations.RunPython(refresh_legal_flatpage_content, noop_reverse),
    ]
