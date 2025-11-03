from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ContractTemplateViewSet, ContractInstanceViewSet


router = DefaultRouter()
router.register(r"templates", ContractTemplateViewSet, basename="templates")
router.register(r"contracts", ContractInstanceViewSet, basename="contracts")
urlpatterns = [path("", include(router.urls))]