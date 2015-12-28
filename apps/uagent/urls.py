from django.conf.urls import include, url
from . import views
from views import RegistrationFormView, LoginFormView, LogoutView

urlpatterns = [
    url(r'^register/', RegistrationFormView.as_view(), name='register_form_view'),
    url(r'^login/', LoginFormView.as_view(), name='login'),
    #url(r'^logout/', LogoutView.as_view(), name='logout'),
]