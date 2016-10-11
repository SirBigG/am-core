from __future__ import unicode_literals

from rest_framework.viewsets import ModelViewSet
from rest_framework.pagination import PageNumberPagination

from api.v1.services.serializers import CommentsSerializer
from api.v1.services.permissions import CommentsCreateUpdatePermission

from core.services.models import Comments
from core.pro_auth.models import User

from django.contrib.contenttypes.models import ContentType


class PostCommentsPagination(PageNumberPagination):
    page_size = 50


# TODO: create logic for update just for comment owner
class PostCommentsViewSet(ModelViewSet):
    """Return node(descendants) of comments for current post object.
       URL: '/api/post/comments/'
       QUERY_PARAMS: post - post id for comments getting, creating etc.
       Examples: GET: /api/post/comments/?post=111 - return all comments for post with 111;
                 GET: /api/post/comment/11/?post=111 - return comment 11 for post 111;
                 POST: /api/post/comments/ - create comment for post(id in request body)."""
    serializer_class = CommentsSerializer
    pagination_class = PostCommentsPagination
    permission_classes = [CommentsCreateUpdatePermission, ]

    def get_queryset(self):
        post_id = self.request.query_params.get('post', None)
        if post_id:
            _root, created = Comments.objects.get_or_create(object_id=post_id,
                                                            user=User.objects.get(email='admin@agromega.in.ua'),
                                                            text='root',
                                                            content_type=ContentType.objects.get(model='post')
                                                            )
            return _root.get_descendants().filter(is_active=True)
        return Comments.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, content_type=ContentType.objects.get(model='post'))
