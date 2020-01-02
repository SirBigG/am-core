from django.urls import include, path


urlpatterns = [
    path('', include('api.v1.classifiers.urls')),
    path('', include('api.v1.posts.urls')),
    path('', include('api.v1.pro_auth.urls')),
    path('', include('api.v1.services.urls')),
    path('', include('api.v1.events.urls')),
]
