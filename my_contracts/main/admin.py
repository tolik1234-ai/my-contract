from django.contrib import admin

from .models import ContractDeployment, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "wallet_address", "preferred_network", "updated_at")
    search_fields = ("user__email", "display_name", "wallet_address")
    list_filter = ("preferred_network",)


@admin.register(ContractDeployment)
class ContractDeploymentAdmin(admin.ModelAdmin):
    list_display = (
        "template_name",
        "network",
        "user",
        "status",
        "transaction_hash",
        "created_at",
    )
    list_filter = ("status", "network")
    search_fields = ("template_name", "transaction_hash", "funding_wallet")
    readonly_fields = ("raw_output", "constructor_arguments")
