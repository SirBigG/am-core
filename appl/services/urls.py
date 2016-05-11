from django.conf.urls import url

from appl.services.views import FeedbackView


urlpatterns = [
    url(r'^feedback/$', FeedbackView.as_view(), name='feedback'),
]
