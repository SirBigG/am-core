"""Exercise the actual server-rendered controls with headless Firefox."""

import os
import tempfile
import unittest
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection

from .test_public_blocks import PublicBlockFixtures


@unittest.skipUnless(os.getenv("AGRO_PUBLIC_BROWSER") == "1", "Requires Firefox and geckodriver")
class PublicBlockBrowserTests(PublicBlockFixtures, StaticLiveServerTestCase):
    def setUp(self):
        import_module("core.catalog.migrations.0005_relation_definitions").bootstrap(
            apps, SimpleNamespace(connection=connection)
        )
        super().setUp()

    def firefox(self):
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service

        runtime = tempfile.TemporaryDirectory(prefix="agro81-firefox-")
        self.addCleanup(runtime.cleanup)
        env = patch.dict(
            os.environ,
            {"XDG_CACHE_HOME": runtime.name, "XDG_CONFIG_HOME": runtime.name, "MOZ_DISABLE_CONTENT_SANDBOX": "1"},
        )
        env.start()
        self.addCleanup(env.stop)
        options = Options()
        options.page_load_strategy = "eager"
        options.add_argument("-headless")
        options.binary_location = "/usr/bin/firefox"
        options.set_preference("layers.acceleration.disabled", True)
        options.set_preference("gfx.webrender.force-disabled", True)
        driver = webdriver.Firefox(options=options, service=Service("/usr/local/bin/geckodriver"))
        self.addCleanup(driver.quit)
        driver.set_page_load_timeout(20)
        return driver

    def test_mobile_keyboard_filter_and_canonical_navigation(self):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait

        self.approved_record()
        self.activate(self.save())
        driver = self.firefox()
        wait = WebDriverWait(driver, 10)
        for width in (1280, 390):
            driver.set_window_size(width, 900)
            driver.get(self.live_server_url + self.path)
            target = driver.find_element(By.ID, "catalog_1_target")
            self.assertTrue(target.is_displayed())
            target.send_keys(Keys.HOME, Keys.ARROW_DOWN, Keys.TAB)
            self.assertEqual(target.get_attribute("value"), str(self.target.pk))
            submit = driver.find_element(By.CSS_SELECTOR, '#related-catalog-1 button[type="submit"]')
            submit.send_keys(Keys.ENTER)
            wait.until(lambda browser: "catalog_1_target=" in browser.current_url)
            robots = driver.find_element(By.CSS_SELECTOR, 'meta[name="robots"]')
            self.assertEqual(robots.get_attribute("content"), "noindex,follow")
            reset = driver.find_element(By.LINK_TEXT, "Скинути фільтри")
            reset.send_keys(Keys.ENTER)
            wait.until(lambda browser: "?" not in browser.current_url)
            card = driver.find_element(By.CSS_SELECTOR, "#related-catalog-1 li a")
            self.assertTrue(card.is_displayed())
            card.send_keys(Keys.ENTER)
            wait.until(lambda browser: "catalog_crop=" in browser.current_url)
            driver.back()
            self.assertTrue(driver.find_element(By.ID, "catalog_1_target").is_displayed())

    def test_mobile_and_desktop_open_sellers_and_return_to_filtered_catalog(self):
        from urllib.parse import urlencode

        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait

        from core.companies.models import Company, Product, RelatedOfferPublication
        from core.posts.models import Post
        from core.utils.tests.factories import LocationFactory

        self.approved_record()
        self.activate(self.save())
        post = Post.objects.get(entity=self.preparation)
        seller = Company.objects.create(
            name="Scoped seller", location=LocationFactory(), website="https://shop.example/"
        )
        product = Product.objects.create(
            post=post,
            category=post.rubric,
            company=seller,
            price=50,
            currency="USD",
            name="Vendor package",
            match_status=Product.MatchStatus.CONFIRMED,
        )
        RelatedOfferPublication.objects.create(
            product=product,
            post=post,
            entity=self.preparation,
            site=self.site,
            country="UA",
            content_locale="uk",
            enabled=True,
            package_label="Пляшка 250 мл",
        )
        driver = self.firefox()
        wait = WebDriverWait(driver, 10)
        query = urlencode({"catalog_1_target": str(self.target.pk), "catalog_1_method": "foliar_spray"})
        filtered = self.live_server_url + self.path + "?" + query
        for width in (1280, 390):
            driver.set_window_size(width, 900)
            driver.get(filtered)
            offers = driver.find_element(By.PARTIAL_LINK_TEXT, "Пропозиції (1)")
            self.assertTrue(offers.is_displayed())
            offers.send_keys(Keys.ENTER)
            wait.until(lambda browser: "/catalog-offers/" in browser.current_url)
            self.assertIn("Пляшка 250 мл", driver.page_source)
            self.assertIn("USD", driver.page_source)
            back = driver.find_element(By.PARTIAL_LINK_TEXT, "Повернутися до добірки")
            back.send_keys(Keys.ENTER)
            wait.until(lambda browser: browser.current_url.startswith(filtered))
            self.assertTrue(driver.find_element(By.PARTIAL_LINK_TEXT, "Пропозиції (1)").is_displayed())
