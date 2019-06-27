from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView

from core.pro_auth.views import Login, Logout, IsAuthenticate, SocialExistUserLogin


app_name = 'pro_auth'

urlpatterns = [
    url(r'^register/social/(?P<backend_name>[\w-]+)/login/$', SocialExistUserLogin.as_view(), name='social-user-exist'),
    url(r'^login/$', Login.as_view(), name='login'),
    url(r'^logout/$', Logout.as_view(), name='logout'),
    url(r'^is-authenticate/$', IsAuthenticate.as_view(), name='is_authenticate'),
    # Rendering index page for all urls starts with /profile/ for personal page.
    url(r'^profile/', login_required(TemplateView.as_view(template_name='personal/personal_index.html')),
        name='personal-index'),
]
