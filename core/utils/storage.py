from django.conf import settings
from django.contrib.staticfiles.storage import StaticFilesStorage
from storages.backends.s3boto3 import S3Boto3Storage


def _versioned_url(url):
    version = settings.MEDIA_VERSION
    if not version or "ckeditor" in url:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}v={version}"


class VersionedStaticFilesStorage(StaticFilesStorage):
    def url(self, name):
        url = super().url(name)
        return _versioned_url(url)


class VersionedS3StaticStorage(S3Boto3Storage):
    """S3 static storage whose public URLs change with each deployed media
    version."""

    def url(self, name, parameters=None, expire=None, http_method=None):
        url = super().url(name, parameters=parameters, expire=expire, http_method=http_method)
        return _versioned_url(url)
