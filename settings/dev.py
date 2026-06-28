import os

from settings.settings import *  # noqa
from settings.settings import INSTALLED_APPS as BASE_INSTALLED_APPS
from settings.settings import MIDDLEWARE as BASE_MIDDLEWARE

ALLOWED_HOSTS = ["*"]

DEBUG = True

ENABLE_ADVERTS = os.getenv("ENABLE_ADVERTS", "0") == "1"
ENABLE_INTERNAL_ADVERTS = os.getenv("ENABLE_INTERNAL_ADVERTS", "1") == "1"
ENABLE_ANALYTICS = os.getenv("ENABLE_ANALYTICS", "0") == "1"
USE_IMGPROXY = os.getenv("USE_IMGPROXY", "0") == "1"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

STATIC_URL = "/static/"
STATIC_ROOT = "/static"

MEDIA_URL = "/media/"
MEDIA_ROOT = "/var/www/media"

# MIDDLEWARE = ['corsheaders.middleware.CorsMiddleware'] + MIDDLEWARE
#
# CORS_ORIGIN_ALLOW_ALL = True
# CORS_ORIGIN_WHITELIST = []

INSTALLED_APPS = [  # noqa
    *BASE_INSTALLED_APPS,
    "silk",
]
MIDDLEWARE = [  # noqa
    *BASE_MIDDLEWARE,
    "silk.middleware.SilkyMiddleware",
]
SILKY_PYTHON_PROFILER = True

SITE_ID = 2
