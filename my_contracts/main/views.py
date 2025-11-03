from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import ContractDeploymentForm, ProfileForm, RegistrationForm
from .models import ContractDeployment
from .services.contract_registry import get_contract_catalog


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
def contracts(request):
    deployments = request.user.deployments.select_related("user").all()
    if request.method == "POST":
        form = ContractDeploymentForm(request.POST, user=request.user)
        if form.is_valid():
            deployment = form.save()
            if deployment.status == deployment.Status.SIMULATED:
                messages.info(request, deployment.status_message)
            elif deployment.status == deployment.Status.FAILED:
                messages.error(request, deployment.status_message)
            else:
                messages.success(request, "Деплой запущен. Следите за статусом ниже.")
            return redirect("contracts")
    else:
        form = ContractDeploymentForm(user=request.user)

    return render(
        request,
        "my_contracts.html",
        {
            "form": form,
            "deployments": deployments,
        },
    )


def docs(request):
    return render(request, "docs.html", {"catalog": get_contract_catalog()})


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
