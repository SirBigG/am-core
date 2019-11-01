from django.conf.urls import url

from core.posts.views import ParentRubricView, PostList, PostDetail, PostSearchView, PostFormView, GalleryView, \
    AddPhotoView

from taggit.models import TagBase
from transliterate import slugify


# TODO: Updated this hack contribute to library
def custom_slugify(self, tag, i=None):
    slug = slugify(tag)
    if i is not None:
        slug += "_%d" % i
    return slug


TagBase.slugify = custom_slugify


urlpatterns = [
    url(r'^search/$', PostSearchView.as_view(), name='post-search-list'),
    url(r'^publication/create/$', PostFormView.as_view(), name='post-add'),
    url(r'^gallery/add/(?P<post_id>[\w-]+)/$', AddPhotoView.as_view(), name="add-photo"),
    url(r'^gallery/(?P<post_id>[\w-]+)/$', GalleryView.as_view(), name="gallery"),
    url(r'^(?P<parent>[\w-]+)/$', ParentRubricView.as_view(), name='parent-category-index'),
    url(r'^(?P<parent>[\w-]+)/(?P<child>[\w-]+)/$', PostList.as_view(), name='posts-list-child'),
    url(r'^(?P<parent>[\w-]+)/(?P<child>[\w-]+)/(?P<slug>[\w-]+)-(?P<id>[\w-]+).html$',
        PostDetail.as_view(), name='post-detail'),
]
