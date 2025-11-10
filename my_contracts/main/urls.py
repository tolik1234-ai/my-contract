from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    contract_catalog_api,
    contracts,
    deployment_collection_api,
    docs,
    home,
    login_view,
    profile,
    register,
    updates,
)

urlpatterns = [
    path('', home, name='home'),
    path('login/', login_view, name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('profile/', profile, name='profile'),
    path('updates/', updates, name='updates'),
    path('contracts/', contracts, name='contracts'),
    path('api/contracts/catalog/', contract_catalog_api, name='contract-catalog-api'),
    path('api/deployments/', deployment_collection_api, name='deployment-collection-api'),
    path('docs/', docs, name='docs'),
    path('register/', register, name='register'),
]
