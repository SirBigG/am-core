from django.shortcuts import render
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import redirect
from django.views.generic.edit import FormView

from forms import UserRegistrationForm


# View for user registration form
class UserRegistrationFormView(FormView):
    template_name = 'uagent/register.html'
    form_class = UserRegistrationForm
    success_url = '/'
    def form_valid(self, form):
        return super(UserRegistrationFormView,self).form_valid(form)
