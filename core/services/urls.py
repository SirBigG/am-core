from django.conf.urls import url

from core.services.views import ReviewInfoView, ReviewsList


app_name = 'services'


urlpatterns = [
    url(r'^reviews/is-reviewed/$', ReviewInfoView.as_view(), name='review-is-reviewed'),
    url(r'^reviews/$', ReviewsList.as_view(), name='review-all-list'),
    url(r'^reviews/(?P<category>[\w-]+)/$', ReviewsList.as_view(), name='review-category-list'),
    url(r'^reviews/(?P<category>[\w-]+)/(?P<slug>[\w-]+)-(?P<object_id>\d+)/$', ReviewsList.as_view(),
        name='review-slug-list'),
]
