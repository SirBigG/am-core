from __future__ import unicode_literals

from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView

from appl.pro_auth.views import RegisterView, Login, Logout, UserEmailConfirm, UserViewSet

from rest_framework.routers import DefaultRouter

urlpatterns = [
    url(r'^register/$', RegisterView.as_view(), name='register'),
    url(r'^login/$', Login.as_view(), name='login'),
    url(r'^logout/$', Logout.as_view(), name='logout'),
    url(r'^confirm/email/(?P<hash>[\w-]+).html$', UserEmailConfirm.as_view(), name='email_confirm'),
    # Rendering index page for all urls starts with /user/<user_id>/ for personal page.
    url(r'^user/(?P<pk>\d+)/', login_required(TemplateView.as_view(template_name='personal/personal_index.html')),
        name='personal-index'),
]

router = DefaultRouter()
router.register('users', UserViewSet)

urlpatterns += router.urls
