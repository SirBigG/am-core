from django.apps import AppConfig


class PostsConfig(AppConfig):
    name = "core.posts"

    def ready(self):
        from core.posts.hub_invalidation import connect_signals

        connect_signals()
