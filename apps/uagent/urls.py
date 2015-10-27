from django.conf.urls import include, url
from . import views
from views import UserRegistrationFormView

urlpatterns = [
    url(r'^register/', UserRegistrationFormView.as_view(), name='register_form_view'),
]