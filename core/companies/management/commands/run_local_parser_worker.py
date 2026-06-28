import os
from types import SimpleNamespace
from urllib.parse import urljoin

import requests
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.companies.parser import (
    create_firefox_driver,
    get_content_from_url,
    parse_data_from_content,
    parse_link_with_js,
)


class ParserWorkerClient:
    def __init__(self, base_url, token, timeout):
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Token {token}"})

    def list_sources(self, category=None, experiment=None, limit=5):
        params = {"limit": limit}
        if category:
            params["category"] = category
        if experiment:
            params["experiment"] = experiment
        response = self.session.get(self.url("api/parser/sources/"), params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def lease(self, source_id, duration_minutes):
        response = self.session.post(
            self.url(f"api/parser/sources/{source_id}/lease/"),
            json={"duration_minutes": duration_minutes},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def submit_results(self, source_id, lease_token, products):
        response = self.session.post(
            self.url(f"api/parser/sources/{source_id}/results/"),
            json={"lease_token": lease_token, "products": products},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def submit_failure(self, source_id, lease_token, error, status=None):
        response = self.session.post(
            self.url(f"api/parser/sources/{source_id}/failure/"),
            json={"lease_token": lease_token, "status": status, "error": str(error)[:2000]},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def url(self, path):
        return urljoin(self.base_url, path)


class Command(BaseCommand):
    help = "Runs a trusted local product parser worker against the AgroMega parser sync API."

    def add_arguments(self, parser):
        parser.add_argument("--base-url", default=os.getenv("PARSER_WORKER_BASE_URL", "http://localhost:8000/"))
        parser.add_argument("--token", default=os.getenv("PARSER_WORKER_TOKEN"))
        parser.add_argument("--category", default=os.getenv("PARSER_WORKER_CATEGORY"))
        parser.add_argument("--experiment", default=os.getenv("PARSER_WORKER_EXPERIMENT"))
        parser.add_argument("--limit", type=int, default=int(os.getenv("PARSER_WORKER_LIMIT", "5")))
        parser.add_argument("--lease-minutes", type=int, default=int(os.getenv("PARSER_WORKER_LEASE_MINUTES", "30")))
        parser.add_argument("--timeout", type=int, default=int(os.getenv("PARSER_WORKER_TIMEOUT", "30")))
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        if not options["token"]:
            raise CommandError("Provide --token or PARSER_WORKER_TOKEN.")

        client = ParserWorkerClient(options["base_url"], options["token"], options["timeout"])
        sources = client.list_sources(
            category=options["category"],
            experiment=options["experiment"],
            limit=options["limit"],
        )
        if not sources:
            self.stdout.write("No parser sources available.")
            return

        browser_driver = None
        parsed_count = 0
        try:
            for source in sources:
                if options["dry_run"]:
                    products, browser_driver = self.parse_source(source, browser_driver)
                    self.stdout.write(f"Parsed {len(products)} products from source {source['id']} (dry run).")
                    parsed_count += len(products)
                    continue

                lease = client.lease(source["id"], options["lease_minutes"])
                try:
                    products, browser_driver = self.parse_source(source, browser_driver)
                except Exception as exc:
                    client.submit_failure(source["id"], lease["lease_token"], exc)
                    self.stderr.write(f"Recorded failure for source {source['id']}: {exc}")
                    continue

                try:
                    client.submit_results(source["id"], lease["lease_token"], products)
                except Exception as exc:
                    self.stderr.write(
                        "Could not confirm result submission for source "
                        f"{source['id']}; not recording parser failure because the server may have saved it: {exc}"
                    )
                    continue

                self.stdout.write(f"Submitted {len(products)} products from source {source['id']}.")
                parsed_count += len(products)
        finally:
            if browser_driver is not None:
                browser_driver.quit()

        self.stdout.write(self.style.SUCCESS(f"Finished local parser worker run. Parsed {parsed_count} products."))

    def parse_source(self, source, browser_driver=None):
        parser_map = source.get("parser_map") or {}
        if not parser_map:
            raise ValueError("Parser source has no parser_map.")

        if source.get("source_type") == "browser":
            if browser_driver is None:
                browser_driver = create_firefox_driver()
            link = SimpleNamespace(
                url=source["url"],
                parser_map=parser_map,
                company=SimpleNamespace(parser_map=parser_map),
                last_crawled=None,
            )
            _link, raw_products = parse_link_with_js(browser_driver, link)
        else:
            content = get_content_from_url(source["url"])
            raw_products = parse_data_from_content(content, parser_map)

        return [
            self.normalize_product(product, source["url"]) for product in raw_products if product.get("name")
        ], browser_driver

    @staticmethod
    def normalize_product(product, source_url):
        product_url = product.get("product_url") or product.get("link") or product.get("url") or ""
        if product_url:
            product_url = urljoin(source_url, product_url)
        return {
            "name": product.get("name"),
            "description": product.get("description") or "",
            "product_url": product_url,
            "price": product.get("price"),
            "min_price": product.get("min_price"),
            "max_price": product.get("max_price"),
            "currency": product.get("currency") or "UAH",
            "observed_at": timezone.now().isoformat(),
            "raw_price": str(product.get("raw_price") or product.get("price") or ""),
            "raw": product,
        }
