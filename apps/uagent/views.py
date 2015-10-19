from django.shortcuts import render
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import redirect
from forms import UserRegistrationForm


# Create your views here.

@csrf_protect
def register(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password1'],
                email=form.cleaned_data['email']
            )
            return redirect('/')
    else:
        form = UserRegistrationForm()
    return render(request, 'uagent/register.html', {'form': form}, )