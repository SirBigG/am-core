"""Single fallback policy for publication metadata, independent of legacy
rows."""

from html import unescape

from django.utils.html import strip_tags
from django.utils.text import Truncator


def resolve_publication_metadata(post):
    title = (post.meta_title or "").strip() or post.title
    description = (post.meta_description or "").strip()
    if not description:
        text = " ".join(unescape(strip_tags(str(post.text or ""))).split())
        description = Truncator(text).chars(160)
    return {"title": title, "description": description}
