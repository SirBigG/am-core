from django.conf.urls import url

from core.posts.views import ParentRubricView, PostList, PostDetail


urlpatterns = [
    url(r'^(?P<parent>[\w-]+)/$', ParentRubricView.as_view(), name='parent-category-index'),
    url(r'^(?P<parent>[\w-]+)/(?P<child>[\w-]+)/$', PostList.as_view(), name='posts-list-child'),
    url(r'^(?P<parent>[\w-]+)/(?P<child>[\w-]+)/(?P<slug>[\w-]+)-(?P<id>[\w-]+).html$',
        PostDetail.as_view(), name='post-detail'),
]
