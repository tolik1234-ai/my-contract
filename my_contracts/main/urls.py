from django.urls import path, include
from .views import *

urlpatterns = [
    path('', home, name='home'),
    path('profile/', profile, name='profile'),
    path('updates/', updates, name='updates'),
    path('my-contacts/', my_contacts, name='my_contacts'),
    path('docs/', docs, name='docs'),
    path('register/', register, name='register'),
]
