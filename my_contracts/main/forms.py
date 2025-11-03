from __future__ import annotations

from typing import Any, Dict

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import ContractDeployment, UserProfile
from .services import contract_registry


class StyledFormMixin:
    """Mixin that appends the dashboard input class to widgets."""

    def _style_fields(self) -> None:
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " form-input").strip()


class RegistrationForm(StyledFormMixin, UserCreationForm):
    full_name = forms.CharField(
        max_length=150,
        label="Full name",
        help_text="Это имя появится в рабочем пространстве и профиле.",
    )
    email = forms.EmailField(label="Email", help_text="Используется для входа в систему")
    wallet_address = forms.CharField(
        max_length=128,
        label="Primary wallet",
        help_text="Адрес кошелька, который будет привязан к вашему аккаунту.",
        required=False,
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Hide the username field from the default UserCreationForm
        self.fields.pop("username", None)
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Confirm password"
        self.fields["password1"].help_text = ""
        self.fields["password2"].help_text = ""
        self._style_fields()
        self.fields['full_name'].widget.attrs.setdefault('placeholder', 'Satoshi Nakamoto')
        self.fields['email'].widget.attrs.setdefault('placeholder', 'ops@mycontracts.dev')
        self.fields['wallet_address'].widget.attrs.setdefault('placeholder', '0x0000...')
        self.fields['password1'].widget.attrs.setdefault('placeholder', '••••••••')
        self.fields['password2'].widget.attrs.setdefault('placeholder', '••••••••')

    def save(self, commit: bool = True) -> User:
        user: User = super().save(commit=False)
        email = self.cleaned_data.get("email", "").lower()
        user.username = email
        user.email = email

        full_name = self.cleaned_data.get("full_name", "").strip()
        if full_name:
            parts = full_name.split()
            user.first_name = parts[0]
            if len(parts) > 1:
                user.last_name = " ".join(parts[1:])

        if commit:
            user.save()
            wallet_address = self.cleaned_data.get("wallet_address", "").strip()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.display_name = full_name or user.get_full_name() or user.username
            profile.wallet_address = wallet_address
            profile.save()
        return user


class ProfileForm(StyledFormMixin, forms.ModelForm):
    email = forms.EmailField(disabled=True, label="Email")

    class Meta:
        model = UserProfile
        fields = ["display_name", "wallet_address", "bio", "preferred_network"]
        labels = {
            "display_name": "Display name",
            "wallet_address": "Wallet address",
            "bio": "About you",
            "preferred_network": "Preferred network",
        }
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["preferred_network"].widget = forms.Select(
            choices=contract_registry.get_network_choices()
        )
        self.fields["display_name"].help_text = "Имя, которое будет видно в интерфейсе."
        self.fields["wallet_address"].help_text = (
            "Адрес, который будет использоваться для подписей. Можно подтянуть из подключенного кошелька."
        )
        self.fields["bio"].help_text = "Короткое описание роли или задач в команде."
        self._style_fields()

    def save(self, commit: bool = True) -> UserProfile:
        profile: UserProfile = super().save(commit=False)
        profile.user = self.user
        if commit:
            profile.save()
        return profile


class ContractDeploymentForm(StyledFormMixin, forms.Form):
    contract_template = forms.ChoiceField(label="Contract blueprint")
    target_network = forms.ChoiceField(label="Network")
    funding_wallet = forms.CharField(
        label="Funding wallet",
        help_text="Кошелёк, из которого будет оплачен деплой.",
    )
    constructor_arguments = forms.CharField(
        label="Constructor parameters",
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text=(
            "JSON с параметрами конструктора. Пример: {\"name\": \"Token\", "
            "\"symbol\": \"TKN\"}."
        ),
        required=False,
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.user: User = kwargs.pop("user")
        super().__init__(*args, **kwargs)

        catalog = contract_registry.get_contract_catalog()
        self.fields["contract_template"].choices = [
            (item.identifier, item.display_name) for item in catalog
        ]

        network_choices = contract_registry.get_network_choices()
        self.fields["target_network"].choices = network_choices

        profile = getattr(self.user, "profile", None)
        if profile and profile.wallet_address:
            self.fields["funding_wallet"].initial = profile.wallet_address

        self._style_fields()
        self.fields['constructor_arguments'].widget.attrs.setdefault('placeholder', '{\n  "name": "Token",\n  "symbol": "TKN"\n}')

    def clean_constructor_arguments(self) -> Dict[str, Any]:
        raw_value = self.cleaned_data.get("constructor_arguments", "").strip()
        if not raw_value:
            return {}
        try:
            return contract_registry.parse_parameters(raw_value)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc

    def save(self) -> ContractDeployment:
        catalog = contract_registry.get_contract_catalog()
        template_id = self.cleaned_data["contract_template"]
        template = next((item for item in catalog if item.identifier == template_id), None)
        if template is None:
            raise forms.ValidationError("Не удалось найти выбранный смарт-контракт.")

        deployment = ContractDeployment.objects.create(
            user=self.user,
            template_id=template.identifier,
            template_name=template.display_name,
            network=self.cleaned_data["target_network"],
            funding_wallet=self.cleaned_data["funding_wallet"],
            constructor_arguments=self.cleaned_data.get("constructor_arguments", {}),
        )

        contract_registry.enqueue_deployment(deployment, template)
        return deployment
