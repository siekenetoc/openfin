from django import forms

from .models import DATEVConfig


class DATEVConfigForm(forms.ModelForm):
    class Meta:
        model = DATEVConfig
        fields = [
            "advisor_number",
            "client_number",
            "fiscal_year",
            "account_length",
            "skr",
            "default_debit_account",
            "default_credit_account",
            "oauth_client_id",
            "oauth_client_secret",
            "oauth_refresh_token",
            "is_active",
        ]
        widgets = {
            "oauth_client_id": forms.PasswordInput(render_value=True),
            "oauth_client_secret": forms.PasswordInput(render_value=True),
            "oauth_refresh_token": forms.PasswordInput(render_value=True),
        }


class AIQueryForm(forms.Form):
    question = forms.CharField(
        label="Frage an das Finanzarchiv",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "z. B. Summe aller Eingänge im Oktober 2026"}),
    )
