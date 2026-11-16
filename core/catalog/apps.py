from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "core.catalog"

    def import_models(self):
        super().import_models()
        # Keep shared identity models separate from the relation storage.
        from . import access_models, application_models, relations  # noqa: F401
