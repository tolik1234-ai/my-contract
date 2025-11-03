from rest_framework import viewsets, permissions
from .models import ContractTemplate, ContractInstance
from .serializers import ContractTemplateSerializer, ContractInstanceSerializer


class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return getattr(obj, "owner_id", None) == request.user.id


class ContractTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ContractTemplate.objects.filter(active=True)
    serializer_class = ContractTemplateSerializer
    permission_classes = [permissions.AllowAny]


class ContractInstanceViewSet(viewsets.ModelViewSet):
    serializer_class = ContractInstanceSerializer
    def get_queryset(self):
        return ContractInstance.objects.filter(owner=self.request.user)
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)