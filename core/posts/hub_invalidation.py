"""Version cached crop contexts when their existing guide collections
change."""

from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_save
from django.utils import timezone

from core.classifier.models import CategoryHub
from core.posts.models import GuideSection, GuideSectionArticle


def remember_previous_source(sender, instance, **kwargs):
    if kwargs.get("raw") or not instance.pk:
        return
    if sender is GuideSection:
        previous = sender.objects.filter(pk=instance.pk).values_list("category_id", flat=True).first()
    else:
        previous = sender.objects.filter(pk=instance.pk).values_list("section__category_id", flat=True).first()
    instance._previous_hub_source = previous


def refresh_guide_hubs(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    if sender is GuideSection:
        category_id = instance.category_id
    else:
        category_id = GuideSection.objects.filter(pk=instance.section_id).values_list("category_id", flat=True).first()
    sources = {value for value in (category_id, getattr(instance, "_previous_hub_source", None)) if value}
    if sources:
        CategoryHub.objects.filter(
            Q(guide_category_id__in=sources) | Q(guide_category__isnull=True, category_id__in=sources)
        ).update(updated=timezone.now())


def connect_signals():
    for model in (GuideSection, GuideSectionArticle):
        key = f"crop-hub-guide-version:{model._meta.label_lower}"
        pre_save.connect(remember_previous_source, sender=model, dispatch_uid=f"{key}:before")
        post_save.connect(refresh_guide_hubs, sender=model, dispatch_uid=f"{key}:save")
        post_delete.connect(refresh_guide_hubs, sender=model, dispatch_uid=f"{key}:delete")
