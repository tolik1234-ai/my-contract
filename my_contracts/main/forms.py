from .models import *
from django.forms import *
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User

class RegisterForm(ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email','wallet_address', 'password1', 'password2']

class LoginForm(AuthenticationForm):
    username = CharField()
    password = CharField(widget=PasswordInput())