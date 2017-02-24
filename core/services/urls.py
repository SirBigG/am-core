from django.conf.urls import url

from core.services.views import FeedbackView, ReviewInfoView, ReviewsList


urlpatterns = [
    url(r'^feedback/$', FeedbackView.as_view(), name='feedback'),
    url(r'^reviews/is-reviewed/$', ReviewInfoView.as_view(), name='review-is-reviewed'),
    url(r'^reviews/$', ReviewsList.as_view(), name='review-all-list'),
    url(r'^reviews/(?P<category>[\w-]+)/$', ReviewsList.as_view(), name='review-category-list'),
    url(r'^reviews/(?P<category>[\w-]+)/(?P<slug>[\w-]+)-(?P<object_id>\d+)/$', ReviewsList.as_view(),
        name='review-slug-list'),
]
