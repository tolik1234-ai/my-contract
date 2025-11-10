from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .forms import ProfileForm, RegistrationForm
from .models import ContractDeployment
from .services.contract_registry import build_catalog_payload, get_contract_catalog


def home(request):
    latest_deployments = ContractDeployment.objects.select_related("user").all()[:3]
    catalog = get_contract_catalog()
    return render(
        request,
        "home.html",
        {
            "catalog": catalog,
            "latest_deployments": latest_deployments,
        },
    )


@login_required
def profile(request):
    profile = request.user.profile
    deployments = request.user.deployments.all()[:5]

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль обновлён.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile, user=request.user)

    form.fields["email"].initial = request.user.email

    return render(
        request,
        "profile.html",
        {
            "form": form,
            "deployments": deployments,
        },
    )


def updates(request):
    return render(request, "updates.html", {"catalog": get_contract_catalog()})


@login_required
@ensure_csrf_cookie
def contracts(request):
    deployments = request.user.deployments.select_related("user").all()
    initial_deployments = [_serialize_deployment(item) for item in deployments]
    initial_catalog = build_catalog_payload()

    config_payload = {
        "catalog": initial_catalog,
        "deployments": initial_deployments,
        "api": {
            "catalog": request.build_absolute_uri(reverse("contract-catalog-api")),
            "deployments": request.build_absolute_uri(reverse("deployment-collection-api")),
        },
        "user": {
            "email": request.user.email,
            "displayName": request.user.profile.display_name
            if hasattr(request.user, "profile")
            else request.user.get_full_name(),
        },
    }

    return render(
        request,
        "my_contracts.html",
        {
            "deployments": deployments,
            "deployment_config": config_payload,
        },
    )


def docs(request):
    return render(request, "docs.html", {"catalog": get_contract_catalog()})


def _serialize_deployment(deployment: ContractDeployment) -> dict:
    return {
        "id": deployment.pk,
        "templateId": deployment.template_id,
        "templateName": deployment.template_name,
        "status": deployment.status,
        "statusLabel": deployment.get_status_display(),
        "statusMessage": deployment.status_message,
        "network": deployment.network,
        "fundingWallet": deployment.funding_wallet,
        "deployerWallet": deployment.deployer_wallet,
        "managerAddress": deployment.manager_address,
        "transactionHash": deployment.transaction_hash,
        "contractAddress": deployment.contract_address,
        "chainId": deployment.chain_id,
        "constructorArguments": deployment.constructor_arguments,
        "metadata": deployment.deployment_metadata,
        "createdAt": deployment.created_at.isoformat() if deployment.created_at else None,
        "updatedAt": deployment.updated_at.isoformat() if deployment.updated_at else None,
        "completedAt": deployment.completed_at.isoformat() if deployment.completed_at else None,
    }


@login_required
@require_http_methods(["GET"])
def contract_catalog_api(request):
    payload = build_catalog_payload()
    return JsonResponse(payload)


@login_required
@require_http_methods(["GET", "POST"])
def deployment_collection_api(request):
    if request.method == "GET":
        deployments = request.user.deployments.select_related("user").all()
        data = [_serialize_deployment(item) for item in deployments]
        return JsonResponse({"deployments": data})

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    template_id = payload.get("template_id") or payload.get("templateId")
    if not template_id:
        return JsonResponse({"error": "Missing template identifier."}, status=400)

    template_name = (
        payload.get("template_name")
        or payload.get("templateName")
        or template_id.replace("_", " ").title()
    )
    network = payload.get("network") or ""
    funding_wallet = payload.get("funding_wallet") or payload.get("fundingWallet")
    deployer_wallet = payload.get("deployer_wallet") or payload.get("deployerWallet")
    constructor_arguments = (
        payload.get("constructor_arguments")
        or payload.get("constructorArguments")
        or {}
    )
    manager_address = payload.get("manager_address") or payload.get("managerAddress")
    chain_id = payload.get("chain_id") or payload.get("chainId")
    transaction_hash = payload.get("transaction_hash") or payload.get("transactionHash")
    contract_address = payload.get("contract_address") or payload.get("contractAddress")
    metadata = payload.get("metadata") or payload.get("deployment_metadata") or {}
    status = payload.get("status") or ContractDeployment.Status.SUCCEEDED
    status_message = payload.get("status_message") or payload.get("statusMessage") or ""

    deployment = ContractDeployment.objects.create(
        user=request.user,
        template_id=template_id,
        template_name=template_name,
        network=network,
        funding_wallet=funding_wallet or deployer_wallet or "",
        constructor_arguments=constructor_arguments,
        manager_address=manager_address or "",
    )

    if status == ContractDeployment.Status.SUCCEEDED:
        deployment.mark_success(
            tx_hash=transaction_hash,
            raw_output=payload.get("raw_output") or payload.get("rawOutput") or "",
            contract_address=contract_address,
            chain_id=chain_id,
            deployer_wallet=deployer_wallet,
            manager_address=manager_address,
            metadata=metadata,
        )
    elif status == ContractDeployment.Status.FAILED:
        deployment.status = ContractDeployment.Status.FAILED
        deployment.status_message = status_message or "Deployment failed."
        if transaction_hash:
            deployment.transaction_hash = transaction_hash
        if contract_address:
            deployment.contract_address = contract_address
        if chain_id:
            deployment.chain_id = str(chain_id)
        if deployer_wallet:
            deployment.deployer_wallet = deployer_wallet
        if metadata:
            deployment.deployment_metadata = metadata
        if manager_address:
            deployment.manager_address = manager_address
        deployment.completed_at = timezone.now()
        deployment.save(
            update_fields=[
                "status",
                "status_message",
                "transaction_hash",
                "contract_address",
                "chain_id",
                "deployer_wallet",
                "deployment_metadata",
                "manager_address",
                "completed_at",
                "updated_at",
            ]
        )
    else:
        deployment.status = status
        deployment.status_message = status_message
        if transaction_hash:
            deployment.transaction_hash = transaction_hash
        if deployer_wallet:
            deployment.deployer_wallet = deployer_wallet
        if manager_address:
            deployment.manager_address = manager_address
        if chain_id:
            deployment.chain_id = str(chain_id)
        if metadata:
            deployment.deployment_metadata = metadata
        deployment.save(
            update_fields=[
                "status",
                "status_message",
                "transaction_hash",
                "deployer_wallet",
                "manager_address",
                "chain_id",
                "deployment_metadata",
                "updated_at",
            ]
        )

    response_payload = _serialize_deployment(deployment)
    return JsonResponse(response_payload, status=201)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('profile')

    next_url = request.GET.get('next')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, 'С возвращением!')
            if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
                return redirect(next_url)
            return redirect('profile')
    else:
        form = AuthenticationForm(request)

    form.fields['username'].label = 'Email'
    form.fields['username'].widget.attrs.update({'autocomplete': 'email', 'placeholder': 'ops@mycontracts.dev'})
    form.fields['username'].widget.attrs.setdefault('class', 'form-input')
    form.fields['password'].label = 'Password'
    form.fields['password'].widget.attrs.update({'autocomplete': 'current-password'})
    form.fields['password'].widget.attrs.setdefault('class', 'form-input')

    return render(request, 'login.html', {'form': form})


def register(request):
    if request.user.is_authenticated:
        return redirect("profile")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Добро пожаловать в рабочее пространство.")
            return redirect("profile")
    else:
        form = RegistrationForm()

    return render(request, "register.html", {"form": form})
