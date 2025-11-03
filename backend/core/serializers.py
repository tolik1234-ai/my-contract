from rest_framework import serializers
from .models import ContractTemplate, ContractInstance


class ContractTemplateSerializer(serializers.ModelSerializer):
class Meta:
model = ContractTemplate
fields = "__all__"


class ContractInstanceSerializer(serializers.ModelSerializer):
template = ContractTemplateSerializer(read_only=True)
class Meta:
model = ContractInstance
fields = "__all__"