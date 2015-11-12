from django.conf.urls import include, url
from . import views
from views import ListPostView

urlpatterns = [
    url(r'^posts/', ListPostView.as_view(), name='list_post_view'),
#TODO: view posts with category things  /<category>/<pk>/ and /posts/<category>/ not /posts/
]