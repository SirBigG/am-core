from django.urls import path
from django.utils.translation import get_language

from core.posts.views import ParentRubricView, PostList, PostDetail, PostSearchView, PostFormView, GalleryView, \
    AddPhotoView, PostListView

from taggit.models import TagBase
from transliterate import slugify


# TODO: Updated this hack contribute to library
def custom_slugify(self, tag, i=None):
    slug = slugify(tag, language_code=get_language())
    if i is not None:
        slug += "_%d" % i
    return slug


TagBase.slugify = custom_slugify

urlpatterns = [
    path('search/', PostSearchView.as_view(), name='post-search-list'),
    path('publication/create/', PostFormView.as_view(), name='post-add'),
    path('gallery/add/<int:post_id>/', AddPhotoView.as_view(), name="add-photo"),
    path('gallery/<int:post_id>/', GalleryView.as_view(), name="gallery"),
    path('<str:parent>/', ParentRubricView.as_view(), name='parent-category-index'),
    path('<str:parent>/<str:child>/', PostListView.as_view(), name='posts-list-view'),
    path('<str:parent>/<str:child>/list/', PostList.as_view(), name='posts-list-child'),
    path('<str:parent>/<str:child>/<str:slug>-<int:pk>.html', PostDetail.as_view(), name='post-detail'),
]
