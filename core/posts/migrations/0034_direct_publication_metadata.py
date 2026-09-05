from django.db import migrations, models


def migrate_legacy_metadata(apps, schema_editor):
    Post = apps.get_model("posts", "Post")
    database = schema_editor.connection.alias
    posts = Post.objects.using(database).filter(meta__isnull=False).select_related("meta")
    for post in posts.iterator(chunk_size=500):
        changes = {}
        if not (post.meta_title or "").strip():
            title = (post.meta.title or "").strip() or (post.meta.h1 or "").strip()
            if title:
                changes["meta_title"] = title
        if not (post.meta_description or "").strip():
            description = (post.meta.description or "").strip()
            if description:
                changes["meta_description"] = description
        if changes:
            Post.objects.using(database).filter(pk=post.pk).update(**changes)


class Migration(migrations.Migration):
    dependencies = [("posts", "0033_merge_20260807_0000")]

    operations = [
        migrations.RenameField(model_name="post", old_name="page_h1", new_name="meta_title"),
        migrations.AlterField(
            model_name="post",
            name="meta_title",
            field=models.CharField(
                max_length=500,
                blank=True,
                null=True,
                verbose_name="Мета-заголовок",
                help_text="Необов’язково. Заголовок у вкладці браузера, H1, соціальних мережах і структурованих даних. Якщо порожньо — канонічна назва.",
            ),
        ),
        migrations.AlterField(
            model_name="post",
            name="meta_description",
            field=models.CharField(
                max_length=500,
                blank=True,
                null=True,
                verbose_name="Мета-опис",
                help_text="Необов’язково. Опис для пошуку, соціальних мереж і структурованих даних. Якщо порожньо — короткий уривок тексту без HTML.",
            ),
        ),
        migrations.AlterField(
            model_name="post",
            name="title",
            field=models.CharField(
                max_length=500,
                verbose_name="Канонічна назва",
                help_text="Назва сорту, породи чи іншої сутності для списків, карток, breadcrumbs та Агромаркету. Також заголовок сторінки за замовчуванням.",
            ),
        ),
        migrations.AlterField(
            model_name="post",
            name="meta",
            field=models.OneToOneField(
                to="services.metadata",
                on_delete=models.SET_NULL,
                blank=True,
                null=True,
                editable=False,
                verbose_name="Архів пов’язаних метаданих",
                related_name="post-meta-data+",
            ),
        ),
        migrations.RunPython(migrate_legacy_metadata, migrations.RunPython.noop),
    ]
