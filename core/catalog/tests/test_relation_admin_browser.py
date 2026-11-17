"""Real browser smoke test for the relation publication workflow."""

import os
import sys
import tempfile
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from core.catalog.relations import RelationRecord, RelationRelease

from . import test_relation_admin


class RelationAdminBrowserTests(StaticLiveServerTestCase):
    editor = staticmethod(test_relation_admin.RelationAdminTests.editor)
    publication_fixture = test_relation_admin.RelationAdminTests.publication_fixture
    publication_rights = test_relation_admin.RelationAdminTests.publication_rights

    def setUp(self):
        import_module("core.catalog.migrations.0005_relation_definitions").bootstrap(
            apps, SimpleNamespace(connection=connection)
        )
        test_relation_admin.RelationAdminTests.setUp(self)
        self.publication_fixture()
        self.publication_rights(review=True, publish=True)

    def test_browser_create_edit_publish_archive_reverse(self):
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.support import expected_conditions as ec
        from selenium.webdriver.support.ui import Select, WebDriverWait

        cache = tempfile.TemporaryDirectory(prefix="agro75-firefox-")
        self.addCleanup(cache.cleanup)
        environment = patch.dict(
            os.environ,
            {"XDG_CACHE_HOME": cache.name, "XDG_CONFIG_HOME": cache.name, "MOZ_DISABLE_CONTENT_SANDBOX": "1"},
        )
        environment.start()
        self.addCleanup(environment.stop)
        options = Options()
        options.add_argument("-headless")
        options.set_preference("layers.acceleration.disabled", True)
        options.set_preference("gfx.webrender.force-disabled", True)
        options.binary_location = "/usr/bin/firefox"
        os.environ["MOZ_DISABLE_CONTENT_SANDBOX"] = "1"
        driver = webdriver.Firefox(
            options=options, service=Service(executable_path="/usr/local/bin/geckodriver", log_output=sys.stdout)
        )
        self.addCleanup(driver.quit)
        wait = WebDriverWait(driver, 15)
        driver.get(self.live_server_url + reverse("admin:login"))
        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        driver.add_cookie({"name": cookie.key, "value": cookie.value, "path": "/"})
        driver.get(self.live_server_url + self.add_url)

        def choose(role, text):
            field = driver.find_element(By.ID, f"id_role_{role}")
            widget = wait.until(lambda browser: field.find_element(By.XPATH, "following-sibling::span"))
            widget.click()
            search = wait.until(
                ec.visibility_of_element_located((By.CSS_SELECTOR, ".select2-container--open .select2-search__field"))
            )
            search.send_keys(text)
            option = wait.until(
                ec.element_to_be_clickable(
                    (By.XPATH, f"//li[contains(@class, 'select2-results__option') and contains(., '{text}')]")
                )
            )
            option.click()

        choose("crop", "Fixture crop")
        choose("cultivar", "Fixture cultivar")
        driver.find_element(By.ID, "id_schema").find_element(By.XPATH, "ancestor::form").find_element(
            By.TAG_NAME, "button"
        ).click()
        wait.until(ec.presence_of_element_located((By.ID, "action_action")))
        record = RelationRecord.objects.get()
        payload = driver.find_element(By.ID, "id_payload")
        payload.clear()
        payload.send_keys('{"browser": true}')
        driver.find_element(By.ID, "id_schema").find_element(By.XPATH, "ancestor::form").find_element(
            By.TAG_NAME, "button"
        ).click()
        wait.until(ec.presence_of_element_located((By.ID, "action_action")))
        self.assertEqual(record.revisions.count(), 2)
        for action in ("submit", "approve", "publish", "archive"):
            field = wait.until(ec.presence_of_element_located((By.ID, "action_action")))
            Select(field).select_by_value(action)
            if action in {"approve", "publish"}:
                Select(driver.find_element(By.ID, "action_content_locale")).select_by_value("uk")
            field.find_element(By.XPATH, "ancestor::form").find_element(By.TAG_NAME, "button").click()
            if action == "archive":
                wait.until(ec.invisibility_of_element_located((By.ID, "action_action")))
            else:
                wait.until(ec.presence_of_element_located((By.ID, "action_action")))
            self.assertNotIn("errorlist", driver.page_source)
        record.refresh_from_db()
        self.assertTrue(record.archived)
        self.assertFalse(RelationRelease.objects.get(record=record).enabled)
        driver.get(self.live_server_url + reverse("admin:catalog_relation_participant", args=[self.crop_entity.pk]))
        wait.until(ec.presence_of_element_located((By.LINK_TEXT, f"cultivar_of · {record.pk}")))
