from django.conf.urls import include, url


urlpatterns = [
    url(r'^', include('api.v1.classifiers.urls')),
    url(r'^', include('api.v1.posts.urls')),
    url(r'^', include('api.v1.pro_auth.urls')),
    url(r'^', include('api.v1.services.urls')),
    url(r'^', include('api.v1.events.urls')),
]
