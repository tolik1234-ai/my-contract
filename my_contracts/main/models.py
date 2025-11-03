from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict, Optional

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=150, blank=True)
    wallet_address = models.CharField(max_length=128, blank=True)
    bio = models.TextField(blank=True)
    preferred_network = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self) -> str:
        return self.display_name or self.user.get_full_name() or self.user.username


class ContractDeployment(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SIMULATED = "simulated", "Simulated"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="deployments")
    template_id = models.CharField(max_length=128)
    template_name = models.CharField(max_length=255)
    network = models.CharField(max_length=64)
    funding_wallet = models.CharField(max_length=128)
    constructor_arguments = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    status_message = models.TextField(blank=True)
    transaction_hash = models.CharField(max_length=120, blank=True)
    raw_output = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.template_name} on {self.network}"

    # --- Deployment orchestration helpers -------------------------------------------------
    def build_arguments_file(self, repo_root: Path) -> Path:
        params_dir = repo_root / ".my_contracts"
        params_dir.mkdir(parents=True, exist_ok=True)
        file_path = params_dir / f"params_{self.pk or uuid.uuid4().hex}.json"
        payload: Dict[str, object] = {
            "constructor": self.constructor_arguments,
            "wallet": self.funding_wallet,
        }
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return file_path

    def mark_simulated(self, reason: str) -> None:
        self.status = self.Status.SIMULATED
        self.status_message = reason
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "status_message", "completed_at", "updated_at"])

    def mark_failed(self, reason: str) -> None:
        self.status = self.Status.FAILED
        self.status_message = reason
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "status_message", "completed_at", "updated_at"])

    @property
    def pretty_arguments(self) -> str:
        if not self.constructor_arguments:
            return '{}'
        return json.dumps(self.constructor_arguments, indent=2, ensure_ascii=False)


    def mark_success(self, tx_hash: Optional[str], raw_output: str = "") -> None:
        self.status = self.Status.SUCCEEDED
        if tx_hash:
            self.transaction_hash = tx_hash
            self.status_message = f"Deployment successful. Tx: {tx_hash}"
        else:
            self.status_message = "Deployment successful."
        if raw_output:
            self.raw_output = raw_output
        self.completed_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "status_message",
                "transaction_hash",
                "raw_output",
                "completed_at",
                "updated_at",
            ]
        )


@receiver(post_save, sender=User)
def create_profile(sender, instance: User, created: bool, **_: object) -> None:
    if created:
        UserProfile.objects.get_or_create(user=instance)
