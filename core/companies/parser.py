import re

import requests
from lxml import html  # nosec


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
