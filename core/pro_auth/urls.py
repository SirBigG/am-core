from django.urls import path
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView

from core.pro_auth.views import (
    Login,
    Logout,
    IsAuthenticate,
    SocialExistUserLogin,
    ChangeProfileView,
    ProfilePostView,
    UpdateProfilePostView,
)


app_name = 'pro_auth'

urlpatterns = [
    path('register/social/<str:backend_name>/login/', SocialExistUserLogin.as_view(), name='social-user-exist'),
    path('profile/', login_required(TemplateView.as_view(template_name='pro_auth/profile/dashboard.html')),
         name='dashboard'),
    path('profile/posts/update/<int:pk>', login_required(UpdateProfilePostView.as_view()), name='profile-posts-update'),
    path('profile/posts', login_required(ProfilePostView.as_view()), name='profile-posts'),
    path('profile/change', login_required(ChangeProfileView.as_view()), name="change-profile"),
    path('login/', Login.as_view(), name='login'),
    path('logout/', Logout.as_view(), name='logout'),
    path('is-authenticate/', IsAuthenticate.as_view(), name='is_authenticate'),
]
