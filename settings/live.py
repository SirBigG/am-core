import os

from .settings import *  # noqa
from .settings import INSTALLED_APPS as BASE_INSTALLED_APPS

INSTALLED_APPS = [
    *BASE_INSTALLED_APPS,
    "storages",
]


def _https_url(value):
    value = value.strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    return f"https://{value}"


AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
AWS_S3_ENDPOINT_URL = _https_url(os.getenv("AWS_S3_ENDPOINT_URL", ""))
AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_S3_CUSTOM_DOMAIN", "")
AWS_QUERYSTRING_AUTH = False
AWS_DEFAULT_ACL = "public-read"
AWS_S3_FILE_OVERWRITE = False

AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "")

AWS_IS_GZIPPED = True
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}
AWS_MEDIA_LOCATION = "media"
AWS_STATIC_LOCATION = "static"


STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "location": AWS_MEDIA_LOCATION,
        },
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "location": AWS_STATIC_LOCATION,
        },
    },
}

STATIC_URL = f"{AWS_S3_ENDPOINT_URL}/{AWS_STATIC_LOCATION}/"

MEDIA_URL = f"{AWS_S3_ENDPOINT_URL}/{AWS_MEDIA_LOCATION}/"
