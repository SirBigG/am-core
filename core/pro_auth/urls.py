from django.urls import path

from core.pro_auth.views import Login, Logout, IsAuthenticate, SocialExistUserLogin


app_name = 'pro_auth'

urlpatterns = [
    path('register/social/<str:backend_name>/login/', SocialExistUserLogin.as_view(), name='social-user-exist'),
    path('login/', Login.as_view(), name='login'),
    path('logout/', Logout.as_view(), name='logout'),
    path('is-authenticate/', IsAuthenticate.as_view(), name='is_authenticate'),
]
