from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import contracts, docs, home, login_view, profile, register, updates

urlpatterns = [
    path('', home, name='home'),
    path('login/', login_view, name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('profile/', profile, name='profile'),
    path('updates/', updates, name='updates'),
    path('contracts/', contracts, name='contracts'),
    path('docs/', docs, name='docs'),
    path('register/', register, name='register'),
]
