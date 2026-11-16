from django.apps import AppConfig


class ClassifierConfig(AppConfig):
    name = "core.classifier"

    def import_models(self):
        super().import_models()
        from . import publication_checks  # noqa: F401
