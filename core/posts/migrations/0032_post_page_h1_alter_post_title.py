from django.db import migrations, models


def copy_metadata_h1_to_post_page_h1(apps, schema_editor):
    Post = apps.get_model("posts", "Post")
    for post in Post.objects.select_related("meta").filter(page_h1__isnull=True, meta__h1__isnull=False).iterator():
        meta_h1 = (post.meta.h1 or "").strip()
        if meta_h1:
            post.page_h1 = meta_h1
            post.save(update_fields=["page_h1"])


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0031_backfill_post_attribute_values"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="page_h1",
            field=models.CharField(
                blank=True,
                help_text="Якщо поле заповнене, саме цей текст буде H1 на сторінці публікації.",
                max_length=500,
                null=True,
                verbose_name="H1 на сторінці публікації",
            ),
        ),
        migrations.AlterField(
            model_name="post",
            name="title",
            field=models.CharField(
                help_text="Коротка назва для списків, карток, breadcrumbs, пошуку та slug.",
                max_length=500,
                verbose_name="Назва у списках",
            ),
        ),
        migrations.RunPython(copy_metadata_h1_to_post_page_h1, migrations.RunPython.noop),
    ]
