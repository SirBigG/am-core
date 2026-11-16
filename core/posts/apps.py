from django.apps import AppConfig


class PostsConfig(AppConfig):
    name = "core.posts"

    def import_models(self):
        super().import_models()
        from . import publication_checks  # noqa: F401

    def ready(self):
        from core.posts.hub_invalidation import connect_signals

        connect_signals()
