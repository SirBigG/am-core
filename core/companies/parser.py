import re
from concurrent.futures import ThreadPoolExecutor
from time import sleep

import requests
from django.utils import timezone
from lxml import html  # nosec
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.firefox import GeckoDriverManager


def extract_price(s):
    match = re.search(r"\d+\.?\d*", s)
    return float(match.group()) if match else None


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

    # Extract data based on XPaths
    extracted_data = {}
    for key, xpath in data_xpaths.items():
        elements = tree.xpath(xpath)
        # Store all found elements' texts (or attributes) in a list
        extracted_data[key] = [element for element in elements] if elements else []
        if key == "price":
            extracted_data[key] = [extract_price(element) for element in extracted_data[key]]
    # make list of objects with the same keys as data_xpaths
    extracted_data = [dict(zip(extracted_data, t)) for t in zip(*extracted_data.values())]
    for data in extracted_data:
        for key, value in data.items():
            if key == "name":
                data[key] = value
    return extracted_data


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
#     driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=opts)  # or use another browser driver like Chrome
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
    from selenium.webdriver import FirefoxOptions

    opts = FirefoxOptions()
    opts.add_argument("--headless")
    # Set up the Selenium WebDriver
    driver = webdriver.Firefox(
        service=FirefoxService(GeckoDriverManager().install()), options=opts
    )  # or use another browser driver like Chrome

    try:
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda link: parse_link_with_js(driver, link), links))
            for link, data in results:
                link.save_result_products(data)
                link.save()
    finally:
        # Close the browser
        driver.quit()
