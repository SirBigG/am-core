import hashlib
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def fetch_json(url):
    cache_key = f"news_api_json_v1:{hashlib.sha256(url.encode()).hexdigest()}"
    cached_payload = cache.get(cache_key)
    if cached_payload is not None:
        return 200, cached_payload

    try:
        response = requests.get(
            url,
            timeout=(settings.NEWS_API_CONNECT_TIMEOUT, settings.NEWS_API_READ_TIMEOUT),
        )
    except requests.RequestException as exc:
        logger.warning("News API request failed: %s", exc, extra={"url": url})
        return None, None

    if response.status_code != 200:
        return response.status_code, None

    try:
        payload = response.json()
    except ValueError:
        logger.exception("News API returned invalid JSON", extra={"url": url})
        return None, None

    cache.set(cache_key, payload, settings.NEWS_API_CACHE_TTL)
    return 200, payload
