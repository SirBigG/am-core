"""Current material approval evidence used by relation publication checks."""

import hashlib
import json

from django.conf import settings
from django.db import models

from .models import Post


def material_digest(post):
    content = {
        "title": post.title,
        "text": post.text,
        "sources": post.sources,
        "source": post.source,
        "author": post.author,
        "publisher": post.publisher_id,
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class PostPublicationApproval(models.Model):
    """Review evidence for the full current material, independent of UI
    locale."""

    post = models.ForeignKey(Post, on_delete=models.PROTECT, related_name="publication_approvals")
    content_digest = models.CharField(max_length=64)
    content_locale = models.CharField(max_length=35)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reviewed_at = models.DateTimeField()
    language_verified = models.BooleanField(default=False)
    legacy_published = models.BooleanField(default=False)
    legacy_site = models.ForeignKey("sites.Site", null=True, blank=True, on_delete=models.PROTECT)
    provenance = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("post", "content_digest", "content_locale"), name="posts_approval_content_locale_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(content_locale="und", language_verified=False, legacy_published=True)
                | (models.Q(language_verified=True) & ~models.Q(content_locale="und") & ~models.Q(content_locale="")),
                name="posts_approval_language_evidence",
            ),
        ]


class SitePostPublication(models.Model):
    site = models.ForeignKey("sites.Site", on_delete=models.PROTECT)
    post = models.ForeignKey(Post, on_delete=models.PROTECT, related_name="site_publications")
    approval = models.ForeignKey(PostPublicationApproval, on_delete=models.PROTECT)
    content_locale = models.CharField(max_length=35)
    category = models.ForeignKey("classifier.Category", on_delete=models.PROTECT)
    canonical_path = models.CharField(max_length=1000)
    enabled = models.BooleanField(default=False)
    publish_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("site", "post", "content_locale"), name="posts_site_material_locale_unique"
            ),
            models.UniqueConstraint(fields=("site", "canonical_path"), name="posts_site_canonical_unique"),
        ]
