# -*- coding: utf-8 -*-

from django.conf.urls import url

from appl.pro_auth.views import RegisterView, Login, Logout, UserEmailConfirm

urlpatterns = [
    url(r'^register/$', RegisterView.as_view(), name='register'),
    url(r'^login/$', Login.as_view(), name='login'),
    url(r'^logout/$', Logout.as_view(), name='logout'),
    url(r'^confirm/email/(?P<hash>[\w-]+).html$', UserEmailConfirm.as_view(), name='email_confirm'),
]
