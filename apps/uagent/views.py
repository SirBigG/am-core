from django.shortcuts import render
from forms import UserRegistrationForm

# Create your views here.


def register(request):
    form = UserRegistrationForm
    return render(request,'main.html',{'form': form})

