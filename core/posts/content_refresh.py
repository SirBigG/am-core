import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

import requests

CHECKSUM_FIELDS = (
    "title",
    "text",
    "work_status",
    "author",
    "source",
    "sources",
    "status",
    "rubric",
    "country",
    "meta_description",
    "meta_title",
    "category_attributes",
)


class ContentRefreshError(RuntimeError):
    pass


class ContentApiClient:
    def __init__(self, base_url, token, timeout=30, session=None):
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Token {token}",
                "Accept": "application/json",
                "User-Agent": "AgroMegaContentRefresh/1.0",
            }
        )

    def list_posts(self, rubric_id, page=1, page_size=100):
        response = self.session.get(
            self.url("api/content/posts/"),
            params={"rubric": rubric_id, "page": page, "page_size": page_size},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ContentRefreshError("Unexpected post-list response shape.")
        return payload

    def get_post(self, post_id):
        response = self.session.get(self.url(f"api/content/posts/{post_id}/"), timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def list_countries(self):
        response = self.session.get(self.url("api/content/countries/"), timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ContentRefreshError("Unexpected country-list response shape.")
        return payload

    def update_post(self, post_id, fields):
        response = self.session.patch(
            self.url(f"api/content/posts/{post_id}/"),
            json=fields,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def url(self, path):
        return urljoin(self.base_url, path)


def inventory_posts(client, rubric_id, output_dir, page_size=100):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    snapshot_path = output_dir / "posts-original.jsonl"

    posts = []
    expected_count = None
    page = 1
    while True:
        payload = client.list_posts(rubric_id=rubric_id, page=page, page_size=page_size)
        if expected_count is None:
            expected_count = payload.get("count")
        page_posts = payload["results"]
        posts.extend(page_posts)
        if not payload.get("next"):
            break
        if not page_posts:
            raise ContentRefreshError("API returned an empty page with a next-page link.")
        page += 1

    if expected_count is None or expected_count != len(posts):
        raise ContentRefreshError(f"Expected {expected_count} posts but fetched {len(posts)}.")

    seen_ids = set()
    publisher_counts = {}
    with snapshot_path.open("x", encoding="utf-8") as snapshot:
        for post in posts:
            post_id = post.get("id")
            if not post_id or post_id in seen_ids:
                raise ContentRefreshError(f"Missing or duplicate post ID: {post_id!r}.")
            seen_ids.add(post_id)
            actual_rubric = (post.get("rubric") or {}).get("id")
            if actual_rubric != rubric_id:
                raise ContentRefreshError(f"Post {post_id} belongs to rubric {actual_rubric}, not {rubric_id}.")
            publisher = str(post.get("publisher"))
            publisher_counts[publisher] = publisher_counts.get(publisher, 0) + 1
            record = {
                "post": post,
                "mutable_checksum": mutable_checksum(post),
            }
            snapshot.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    staff_detail_access = False
    if posts:
        staff_detail_access = client.get_post(posts[0]["id"]).get("id") == posts[0]["id"]

    summary = {
        "rubric_id": rubric_id,
        "post_count": len(posts),
        "pages_fetched": page,
        "publisher_counts": publisher_counts,
        "staff_detail_access_verified": staff_detail_access,
        "snapshot": snapshot_path.name,
    }
    (output_dir / "inventory-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def mutable_checksum(post):
    mutable = {field: post.get(field) for field in CHECKSUM_FIELDS}
    encoded = json.dumps(mutable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
