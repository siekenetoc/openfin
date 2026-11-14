from django import forms

from .models import ERPConfig


class ERPConfigForm(forms.ModelForm):
    class Meta:
        model = ERPConfig
        fields = [
            "name",
            "erp_base_url",
            "api_key",
            "api_secret",
            "webhook_secret",
            "company",
            "default_currency",
            "default_bank_account",
            "transit_account_stripe",
            "transit_account_paypal",
            "transit_account_wero",
            "skonto_account",
            "default_debit_account",
            "default_credit_account",
            "default_discount_rate",
            "default_discount_days",
            "is_active",
        ]
        widgets = {
            "api_key": forms.PasswordInput(render_value=True),
            "api_secret": forms.PasswordInput(render_value=True),
            "webhook_secret": forms.PasswordInput(render_value=True),
        }
