from django.conf.urls import url

from core.services.views import FeedbackView


urlpatterns = [
    url(r'^feedback/$', FeedbackView.as_view(), name='feedback'),
]
