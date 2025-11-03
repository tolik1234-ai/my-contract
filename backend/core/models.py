from django.db import models
from django.contrib.auth.models import User


class Wallet(models.Model):
user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wallets")
address = models.CharField(max_length=64, db_index=True)
chain = models.CharField(max_length=32, default="sepolia")
def __str__(self): return f"{self.address}@{self.chain}"


class ContractTemplate(models.Model):
TEMPLATE_CHOICES = [("vesting","Vesting"),("airdrop20","Airdrop ERC20"),("airdrop721","Airdrop ERC721")]
template_id = models.CharField(max_length=32, choices=TEMPLATE_CHOICES)
name = models.CharField(max_length=64)
version = models.PositiveIntegerField(default=1)
risk_score = models.PositiveSmallIntegerField(default=0)
active = models.BooleanField(default=True)
def __str__(self): return f"{self.template_id}@v{self.version}"


class ContractInstance(models.Model):
owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="contracts")
template = models.ForeignKey(ContractTemplate, on_delete=models.PROTECT)
address = models.CharField(max_length=64, db_index=True)
chain = models.CharField(max_length=32, default="sepolia")
deployed_at = models.DateTimeField(auto_now_add=True)
metadata = models.JSONField(default=dict)
def __str__(self): return f"{self.address} ({self.template})"