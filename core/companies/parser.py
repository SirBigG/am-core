import os
import re
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
from time import sleep

import requests
from django.utils import timezone
from lxml import html  # nosec
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

PARSER_CONFIG_KEYS = {"item", "snapshot_complete"}


def extract_price(value):
    """Return a backward-compatible float normalized from common shop price
    text."""
    if value is None:
        return None
    compact = re.sub(r"[\s\u00a0\u202f]", "", str(value))
    match = re.search(r"[-+]?\d[\d.,]*", compact)
    if not match:
        return None
    number = match.group()
    if "," in number and "." in number:
        decimal_separator = "," if number.rfind(",") > number.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        number = number.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in number:
        number = number.replace(",", ".")
    try:
        return float(Decimal(number))
    except InvalidOperation:
        return None


def _xpath_value(value):
    if hasattr(value, "text_content"):
        value = value.text_content()
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return " ".join(value.split())
    return value


def _relative_xpath(xpath):
    if xpath.startswith("//"):
        return f".{xpath}"
    return xpath


def _parse_item_nodes(tree, data_xpaths, item_xpath):
    parsed = []
    for item_node in tree.xpath(item_xpath):
        product = {}
        for key, xpath in data_xpaths.items():
            if key in PARSER_CONFIG_KEYS:
                continue
            values = item_node.xpath(_relative_xpath(xpath))
            value = _xpath_value(values[0]) if values else None
            product[key] = extract_price(value) if key in {"price", "min_price", "max_price"} else value
        parsed.append(product)
    return parsed


def _parse_legacy_lists(tree, data_xpaths):
    """Preserve legacy global XPath configs without silently misaligning
    rows."""
    extracted = {}
    for key, xpath in data_xpaths.items():
        if key in PARSER_CONFIG_KEYS:
            continue
        values = [_xpath_value(value) for value in tree.xpath(xpath)]
        if key in {"price", "min_price", "max_price"}:
            values = [extract_price(value) for value in values]
        extracted[key] = values

    name_count = len(extracted.get("name", []))
    if not name_count:
        return []
    for key, values in extracted.items():
        if values and len(values) != name_count:
            raise ValueError(
                f"Parser XPath result count mismatch: name returned {name_count}, {key} returned {len(values)}. "
                "Configure an item XPath with relative field selectors to avoid incorrect product pairing."
            )
    return [
        {key: values[index] if values else None for key, values in extracted.items()} for index in range(name_count)
    ]


def parse_data_from_content(html_content, data_xpaths):
    """Parses data from a saved HTML file given a dictionary of XPaths,
    supporting multiple elements per XPath.

    Parameters:
    - file_path: The path to the saved HTML file.
    - data_xpaths: A dictionary where keys are data field names and values are XPaths to the elements.

    Returns:
    A dictionary with the same keys as data_xpaths, but the values are lists of extracted data.
    """
    # Parse the HTML
    tree = html.fromstring(html_content)

    item_xpath = data_xpaths.get("item")
    if item_xpath:
        return _parse_item_nodes(tree, data_xpaths, item_xpath)
    return _parse_legacy_lists(tree, data_xpaths)


def get_content_from_url(url):
    """Fetches the content of a webpage given its URL.

    Parameters:
    - url: The URL of the webpage.

    Returns:
    The content of the webpage as a string.
    """
    response = requests.get(url, timeout=20)
    if response.status_code != 200:
        raise ValueError(f"Failed to fetch content from {url}. Status code: {response.status_code}")
    return response.content.decode("utf-8")


# def parse_link_with_js(link):
#     from selenium.webdriver import FirefoxOptions
#
#     opts = FirefoxOptions()
#     opts.add_argument("--headless")
#     # Set up the Selenium WebDriver
#     driver = create_firefox_driver()  # or use another browser driver like Chrome
#
#     try:
#         # Navigate to the URL
#         driver.get(link.url)
#
#         # Wait for the JavaScript to load
#         WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
#
#         # Additional sleep to ensure all JS scripts are loaded
#         sleep(5)
#
#         # Extract the HTML content of the page
#         html_content = driver.page_source
#
#         # Parse the HTML content
#         data = parse_data_from_content(html_content, link.parser_map or link.company.parser_map)
#
#
#         return data
#     finally:
#         link.last_crawled = timezone.now()
#         # Close the browser
#         driver.quit()


def create_firefox_driver():
    from selenium.webdriver import FirefoxOptions

    opts = FirefoxOptions()
    opts.add_argument("--headless")
    service = FirefoxService(executable_path=os.environ.get("GECKODRIVER_PATH", "geckodriver"))
    return webdriver.Firefox(service=service, options=opts)


def parse_link_with_js(driver, link):
    try:
        # Navigate to the URL
        driver.get(link.url)

        # Wait for the JavaScript to load
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Additional sleep to ensure all JS scripts are loaded
        sleep(5)

        # Extract the HTML content of the page
        html_content = driver.page_source

        # Parse the HTML content
        data = parse_data_from_content(html_content, link.parser_map or link.company.parser_map)
        link.last_crawled = timezone.now()
        return link, data
    finally:
        link.last_crawled = timezone.now()


def parse_many_links_with_same_browser(links):
    # Set up the Selenium WebDriver
    driver = create_firefox_driver()  # or use another browser driver like Chrome

    try:
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda link: parse_link_with_js(driver, link), links))
            for link, data in results:
                link.save_result_products(data)
                link.save()
    finally:
        # Close the browser
        driver.quit()
