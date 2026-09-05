import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from core.posts.content_refresh import ContentApiClient, ContentRefreshError, inventory_posts, mutable_checksum
from core.posts.management.commands.publish_content_refresh_pilot import parse_review, sources_html, validate_fields


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(next(self.responses))


def post(post_id, rubric_id=955, publisher=1):
    return {
        "id": post_id,
        "title": f"Breed {post_id}",
        "text": "<p>Legacy</p>",
        "publisher": publisher,
        "rubric": {"id": rubric_id, "slug": "sheep", "title": "Sheep"},
    }


class ContentRefreshInventoryTests(TestCase):
    def test_exports_all_pages_with_checksums_and_staff_probe(self):
        first = post(1)
        second = post(2, publisher=9)
        session = FakeSession(
            [
                {"count": 2, "next": "next", "results": [first]},
                {"count": 2, "next": None, "results": [second]},
                first,
            ]
        )
        client = ContentApiClient("https://example.test", "secret", session=session)

        with TemporaryDirectory() as temporary_dir:
            output_dir = f"{temporary_dir}/run"
            summary = inventory_posts(client, 955, output_dir, page_size=1)
            with open(f"{output_dir}/posts-original.jsonl", encoding="utf-8") as snapshot:
                records = [json.loads(line) for line in snapshot]

        self.assertEqual(summary["post_count"], 2)
        self.assertEqual(summary["publisher_counts"], {"1": 1, "9": 1})
        self.assertTrue(summary["staff_detail_access_verified"])
        self.assertEqual(records[0]["mutable_checksum"], mutable_checksum(first))
        self.assertNotIn("secret", repr(session.calls))

    def test_rejects_posts_from_another_rubric(self):
        session = FakeSession([{"count": 1, "next": None, "results": [post(1, rubric_id=12)]}])
        client = ContentApiClient("https://example.test", "secret", session=session)

        with TemporaryDirectory() as temporary_dir:
            output_dir = f"{temporary_dir}/run"
            with self.assertRaisesRegex(ContentRefreshError, "rubric 12"):
                inventory_posts(client, 955, output_dir)

    def test_checksum_changes_when_mutable_content_changes(self):
        original = post(1)
        changed = {**original, "text": "<p>Updated</p>"}

        self.assertNotEqual(mutable_checksum(original), mutable_checksum(changed))

    def test_sources_html_is_safe_ckeditor_markup(self):
        rendered = sources_html(["https://www.fao.org/example"])

        validate_fields({"title": "Авасі | Awassi", "text": "<p>Текст</p>", "sources": rendered})
        self.assertIn('rel="noopener noreferrer"', rendered)

    def test_review_parser_converts_parenthesized_english_title(self):
        review = """## 1 — Тексель (Texel)

- Proposed title: **Тексель (Texel)**
- Proposed country: Netherlands
- Evidence: [Source](https://example.test/source)

```html
<p>Text</p>
```
"""
        with TemporaryDirectory() as temporary_dir:
            path = f"{temporary_dir}/review.md"
            with open(path, "w", encoding="utf-8") as target:
                target.write(review)
            parsed = parse_review(Path(path))

        self.assertEqual(parsed[1]["title"], "Тексель | Texel")


class MetadataChecksumTests(TestCase):
    def test_metadata_edits_change_snapshot_checksum(self):
        original = post(1)
        for field in ("meta_title", "meta_description"):
            self.assertNotEqual(mutable_checksum(original), mutable_checksum({**original, field: "SEO edit"}))
        self.assertEqual(
            mutable_checksum(original), mutable_checksum({**original, "resolved_metadata": {"title": "preview"}})
        )
