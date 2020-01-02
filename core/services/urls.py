from django.urls import path

from core.services.views import ReviewInfoView, ReviewsList


app_name = 'services'


urlpatterns = [
    path('reviews/is-reviewed/', ReviewInfoView.as_view(), name='review-is-reviewed'),
    path('reviews/', ReviewsList.as_view(), name='review-all-list'),
    path('reviews/<str:category>/', ReviewsList.as_view(), name='review-category-list'),
    path('reviews/<str:category>/<str:slug>-<int:object_id>/', ReviewsList.as_view(), name='review-slug-list'),
]
