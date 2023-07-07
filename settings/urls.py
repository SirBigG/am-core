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
from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic import TemplateView
# from django.contrib.auth.decorators import login_required
from django.conf.urls.i18n import i18n_patterns

from core.posts import views
# from core.news.views import AdvertListView
from core.services.views import FeedbackView

urlpatterns = i18n_patterns(
    path('', views.IndexView.as_view(), name='index'),
    path(f'admin{settings.ADMIN_HASH}/', admin.site.urls),
    path('rosetta/', include('rosetta.urls')),
    path('comment/', include('comment.urls')),
    path('api/', include('comment.api.urls')),
    path('sitemap.xml', views.SiteMap.as_view(), name='sitemap'),
    path('categories/', TemplateView.as_view(template_name="categories.html"), name='categories'),
    path('create/', TemplateView.as_view(template_name="add.html"), name='add'),
    path('social/', include('social_django.urls', namespace='social')),
    path('api-auth/', include('rest_framework.urls',
                              namespace='rest_framework')),
    path('page/', include('django.contrib.flatpages.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('feedback/', FeedbackView.as_view(), name="feedback-form"),
    path('service/', include('core.services.urls')),
    path('api/', include('api.v1.urls')),
    path('events/', include('core.events.urls', namespace='events')),
    path('news/', include('core.news.urls', namespace='news')),
    path('adverts/', include("core.adverts.urls", namespace='adverts')),
    path('diaries/', include("core.diary.urls", namespace='diaries')),
    # path('adverts/<str:category>/', AdvertListView.as_view(), name="adverts-list"),
    # path('adverts/', AdvertListView.as_view(), name="adverts-list"),
    # Rendering index page for all urls starts with /profile/ for personal page.
    # path('profile/', login_required(TemplateView.as_view(template_name='personal/personal_index.html')),
    #      name='personal-index'),
    path('', include('core.classifier.urls')),
    path('', include('core.pro_auth.urls', namespace='pro_auth')),
    path('', include('core.posts.urls')),
    prefix_default_language=False
)

# For returning errors pages. Need to be the last.
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += staticfiles_urlpatterns()

if settings.DEBUG:
    urlpatterns = [path('silk/', include('silk.urls', namespace='silk')),] + urlpatterns
