from django.conf import settings
from django.contrib.staticfiles.storage import StaticFilesStorage


class VersionedStaticFilesStorage(StaticFilesStorage):
    def url(self, name):
        url = super().url(name)
        # skip versions for ckeditor
        if "ckeditor" in url:
            return url
        return f"{url}?v={settings.MEDIA_VERSION}"
