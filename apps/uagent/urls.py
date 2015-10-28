from django.conf.urls import include, url
from . import views
from views import UserRegistrationFormView, UserAuthFormView

urlpatterns = [
    url(r'^register/', UserRegistrationFormView.as_view(), name='register_form_view'),
    url(r'^login/', UserAuthFormView.as_view(), name='login_view')
]