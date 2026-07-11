from django.urls import include, path

urlpatterns = [
    path("content/", include("api.v1.content.urls")),
    path("", include("api.v1.classifiers.urls")),
    path("", include("api.v1.posts.urls")),
    path("", include("api.v1.pro_auth.urls")),
    path("", include("api.v1.services.urls")),
    path("", include("api.v1.events.urls")),
    path("", include("api.v1.parser.urls")),
    path("registry/", include("api.v1.registry.urls")),
]
