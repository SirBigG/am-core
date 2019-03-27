"""golub_portal URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf.urls import include, url
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from core.posts import views
from core.news.views import AdvertListView


urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^jet/', include('jet.urls', 'jet')),
    url(r'^admin/', admin.site.urls),
    url(r'^rosetta/', include('rosetta.urls')),
    url(r'^sitemap\.xml', views.SiteMap.as_view(), name='sitemap'),
    url(r'social/', include('social_django.urls', namespace='social')),
    url(r'^api-auth/', include('rest_framework.urls',
                               namespace='rest_framework')),
    url('^page/', include('django.contrib.flatpages.urls')),
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^service/', include('core.services.urls')),
    url(r'^api/', include('api.v1.urls')),
    url(r'^events/', include('core.events.urls', namespace='events')),
    url(r'^news/', include('core.news.urls', namespace='news')),
    url(r'adverts/(?P<category>[\w-]+)/$', AdvertListView.as_view(), name="adverts-list"),
    url(r'adverts/$', AdvertListView.as_view(), name="adverts-list"),
    url(r'^', include('core.classifier.urls')),
    url(r'^', include('core.pro_auth.urls', namespace='pro_auth')),
    url(r'^', include('core.posts.urls')),
]

# For returning errors pages. Need to be the last.
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += staticfiles_urlpatterns()
