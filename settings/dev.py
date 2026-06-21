import os

from settings.settings import *  # noqa

ALLOWED_HOSTS = ["*"]

DEBUG = True

ENABLE_ADVERTS = os.getenv("ENABLE_ADVERTS", "0") == "1"
ENABLE_ANALYTICS = os.getenv("ENABLE_ANALYTICS", "0") == "1"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

STATIC_URL = "/static/"
STATIC_ROOT = "/static"

MEDIA_URL = "/media/"
MEDIA_ROOT = "/media"

# MIDDLEWARE = ['corsheaders.middleware.CorsMiddleware'] + MIDDLEWARE
#
# CORS_ORIGIN_ALLOW_ALL = True
# CORS_ORIGIN_WHITELIST = []

INSTALLED_APPS += [  # noqa
    "silk",
]
MIDDLEWARE += [  # noqa
    "silk.middleware.SilkyMiddleware",
]
SILKY_PYTHON_PROFILER = True

SITE_ID = 2
