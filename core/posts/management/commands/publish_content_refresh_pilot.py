import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError

from core.posts.content_refresh import ContentApiClient, mutable_checksum

ALLOWED_TAGS = {"p", "h2", "h3", "ul", "ol", "li", "strong", "em", "a"}
ALLOWED_ATTRIBUTES = {"a": {"href", "rel", "target"}}
COUNTRY_ALIASES = {
    "Algeria": {"algeria", "алжир"},
    "Afghanistan": {"afghanistan", "афганістан"},
    "Australia": {"australia", "австралія"},
    "Austria": {"austria", "австрія"},
    "Barbados": {"barbados", "барбадос"},
    "Brazil": {"brazil", "бразилія"},
    "Canada": {"canada", "канада"},
    "China": {"china", "китай"},
    "Denmark": {"denmark", "данія"},
    "Egypt": {"egypt", "єгипет"},
    "Ethiopia": {"ethiopia", "ефіопія"},
    "France": {"france", "франція"},
    "Germany": {"germany", "німеччина"},
    "Greece": {"greece", "греція"},
    "Hungary": {"hungary", "угорщина"},
    "Croatia": {"croatia", "хорватія"},
    "Czech Republic": {"czech-republic", "czech republic", "czechia", "чехія"},
    "Iceland": {"iceland", "ісландія"},
    "Indonesia": {"indonesia", "індонезія"},
    "Italy": {"italy", "італія"},
    "Finland": {"finland", "фінляндія"},
    "Ireland": {"ireland", "ірландія"},
    "Iran": {"iran", "іран"},
    "Pakistan": {"pakistan", "пакистан"},
    "Portugal": {"portugal", "португалія"},
    "Russia": {"russia", "russian federation", "росія", "російська федерація"},
    "Romania": {"romania", "румунія"},
    "Kenya": {"kenya", "кенія"},
    "Kyrgyzstan": {"kyrgyzstan", "киргизстан", "киргизія"},
    "Slovenia": {"slovenia", "словенія"},
    "Somalia": {"somalia", "сомалі"},
    "Spain": {"spain", "іспанія"},
    "Switzerland": {"switzerland", "швейцарія"},
    "Sweden": {"sweden", "швеція"},
    "Turkey": {"turkey", "turkiye", "türkiye", "туреччина"},
    "United Kingdom": {"united-kingdom", "united kingdom", "uk", "велика британія"},
    "United States": {"united-states", "united states", "usa", "us", "сша"},
    "Netherlands": {"netherlands", "the-netherlands", "нідерланди"},
    "Norway": {"norway", "норвегія"},
    "New Zealand": {"new-zealand", "new zealand", "nz", "нова зеландія"},
    "South Africa": {"south-africa", "south africa", "південно-африканська республіка", "пар"},
}


class SafeHtmlValidator(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            raise ValueError(f"Disallowed HTML tag: {tag}")
        allowed = ALLOWED_ATTRIBUTES.get(tag, set())
        for name, value in attrs:
            if name not in allowed:
                raise ValueError(f"Disallowed attribute {name} on {tag}")
            if name == "href":
                parsed = urlparse(value)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ValueError(f"Unsafe source URL: {value}")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


class Command(BaseCommand):
    help = "Validates and optionally publishes the approved five-post sheep content pilot."

    def add_arguments(self, parser):
        parser.add_argument("run_dir")
        parser.add_argument("--review-file", default="candidates/review.md")
        parser.add_argument("--base-url", default=os.getenv("CONTENT_REFRESH_BASE_URL") or os.getenv("SITE_URL"))
        parser.add_argument("--token", default=os.getenv("AGROMEGA_CONTENT_API_TOKEN"))
        parser.add_argument("--timeout", type=int, default=30)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument(
            "--confirm-posts",
            help="Required with --apply; exact comma-separated IDs being authorized.",
        )

    def handle(self, *args, **options):
        if not options["base_url"] or not options["token"]:
            raise CommandError("The API base URL and AGROMEGA_CONTENT_API_TOKEN are required.")
        run_dir = Path(options["run_dir"])
        candidates = parse_review(run_dir / options["review_file"])
        originals = load_originals(run_dir / "posts-original.jsonl")
        apply_latest_published_checksums(originals, run_dir / "pilot-publish-results.json")
        expected_ids = set(candidates)
        if options["apply"]:
            confirmed = parse_confirmed_ids(options["confirm_posts"])
            if confirmed != expected_ids:
                raise CommandError(f"--confirm-posts must contain exactly: {','.join(map(str, sorted(expected_ids)))}")

        client = ContentApiClient(options["base_url"], options["token"], options["timeout"])
        country_ids = resolve_country_ids(client.list_countries(), candidates.values())
        results = []
        for post_id, candidate in candidates.items():
            current = client.get_post(post_id)
            original = originals.get(post_id)
            if original is None:
                raise CommandError(f"Post {post_id} is missing from the original snapshot.")
            if mutable_checksum(current) != original["mutable_checksum"]:
                raise CommandError(f"Post {post_id} changed after inventory; stopping without updating it.")
            fields = {
                "title": candidate["title"],
                "text": candidate["text"],
                "sources": sources_html(candidate["sources"]),
            }
            if candidate["country"]:
                fields["country"] = country_ids[candidate["country"]]
            validate_fields(fields)
            result = {"post_id": post_id, "mode": "dry-run", "fields": sorted(fields)}
            if options["apply"]:
                updated = client.update_post(post_id, fields)
                for field, expected in fields.items():
                    actual = updated[field]
                    if field == "country":
                        actual = (actual or {}).get("id")
                    if actual != expected:
                        raise CommandError(f"Post {post_id} failed readback verification for {field}.")
                result["mode"] = "updated"
                result["new_checksum"] = mutable_checksum(updated)
            results.append(result)
            self.stdout.write(f"{result['mode']}: post {post_id} -> {candidate['title']}")

        review_stem = Path(options["review_file"]).stem
        result_name = (
            f"{review_stem}-publish-results.json" if options["apply"] else f"{review_stem}-dry-run-results.json"
        )
        (run_dir / result_name).write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Pilot {('publish' if options['apply'] else 'dry run')} complete."))


def parse_review(path):
    content = path.read_text(encoding="utf-8")
    sections = re.split(r"(?=^## \d+ — )", content, flags=re.MULTILINE)[1:]
    candidates = {}
    for section in sections:
        post_id = int(re.match(r"## (\d+)", section).group(1))
        title_match = re.search(r"^- Proposed title: \*\*(.+)\*\*$", section, re.MULTILINE)
        country_match = re.search(r"^- Proposed country: (.+)$", section, re.MULTILINE)
        evidence_match = re.search(r"^- Evidence: (.+)$", section, re.MULTILINE)
        html_match = re.search(r"```html\n(.*?)\n```", section, re.DOTALL)
        if not all((title_match, country_match, evidence_match, html_match)):
            raise CommandError(f"Candidate section {post_id} is incomplete.")
        title = re.sub(r" \(([^()]+)\)$", r" | \1", title_match.group(1))
        country_value = country_match.group(1).strip()
        country = None if country_value.startswith("leave unset") else country_value
        sources = re.findall(r"\[[^]]+\]\((https?://[^)]+)\)", evidence_match.group(1))
        candidates[post_id] = {"title": title, "country": country, "sources": sources, "text": html_match.group(1)}
    return candidates


def load_originals(path):
    with path.open(encoding="utf-8") as source:
        records = [json.loads(line) for line in source]
    return {record["post"]["id"]: record for record in records}


def apply_latest_published_checksums(originals, result_path):
    if not result_path.exists():
        return
    for result in json.loads(result_path.read_text(encoding="utf-8")):
        if result.get("mode") == "updated" and result.get("new_checksum") and result["post_id"] in originals:
            originals[result["post_id"]]["mutable_checksum"] = result["new_checksum"]


def resolve_country_ids(countries, candidates):
    normalized = {}
    for country in countries:
        for value in (country.get("slug"), country.get("short_slug"), country.get("title")):
            if value:
                normalized[value.casefold()] = country["id"]
    resolved = {}
    for candidate in candidates:
        name = candidate["country"]
        if not name or name in resolved:
            continue
        matches = {normalized[alias.casefold()] for alias in COUNTRY_ALIASES[name] if alias.casefold() in normalized}
        if len(matches) != 1:
            raise CommandError(f"Could not uniquely resolve country {name!r} through the countries API.")
        resolved[name] = matches.pop()
    return resolved


def sources_html(urls):
    links = "".join(f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a></li>' for url in urls)
    return f"<ul>{links}</ul>"


def validate_fields(fields):
    if not fields["title"] or len(fields["title"]) > 500:
        raise CommandError("Candidate title is empty or too long.")
    for field in ("text", "sources"):
        validator = SafeHtmlValidator()
        try:
            validator.feed(fields[field])
            validator.close()
        except ValueError as exc:
            raise CommandError(f"Invalid {field} HTML: {exc}") from exc


def parse_confirmed_ids(value):
    if not value:
        return set()
    try:
        return {int(item) for item in value.split(",")}
    except ValueError as exc:
        raise CommandError("--confirm-posts must contain comma-separated integer IDs.") from exc
