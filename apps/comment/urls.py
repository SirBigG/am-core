from django.conf.urls import include, url
from .views import CommentValidate

urlpatterns = [
    url(r'^validate/$', CommentValidate.as_view(), name='list_post_view'),
]
