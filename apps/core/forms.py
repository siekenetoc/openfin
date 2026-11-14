from __future__ import annotations

from django import forms
from django.core.validators import RegexValidator

from .models import Domain, Tenant

schema_validator = RegexValidator(
    regex=r"^[a-z][a-z0-9_]{2,62}$",
    message="Schema darf nur Kleinbuchstaben, Zahlen und Unterstriche enthalten (3–63 Zeichen).",
)


class TenantCreateForm(forms.Form):
    name = forms.CharField(max_length=120, label="Mandantenname")
    schema_name = forms.CharField(
        max_length=63,
        label="Schema-Name (tenant_…)",
        validators=[schema_validator],
        help_text="Technischer PostgreSQL-Schema-Name, z. B. firma_a.",
    )
    domain = forms.CharField(
        max_length=253,
        label="Primäre Domain",
        help_text="z. B. firma-a.localhost oder fin.firma-a.de",
    )
    admin_username = forms.CharField(max_length=150, label="Admin-Benutzername")
    admin_email = forms.EmailField(label="Admin-E-Mail")
    admin_password = forms.CharField(widget=forms.PasswordInput, min_length=8, label="Admin-Passwort")

    def clean_schema_name(self):
        schema = self.cleaned_data["schema_name"]
        if Tenant.objects.filter(schema_name=schema).exists():
            raise forms.ValidationError("Dieses Schema existiert bereits.")
        return schema

    def clean_domain(self):
        domain = self.cleaned_data["domain"].strip().lower()
        if Domain.objects.filter(domain=domain).exists():
            raise forms.ValidationError("Diese Domain ist bereits einem Mandanten zugeordnet.")
        return domain

    def save(self):
        from django.contrib.auth import get_user_model

        data = self.cleaned_data
        tenant = Tenant.objects.create(
            name=data["name"],
            schema_name=data["schema_name"],
            slug=data["schema_name"],
            on_trial=True,
        )
        Domain.objects.create(domain=data["domain"], tenant=tenant, is_primary=True)
        User = get_user_model()
        User.objects.create_user(
            username=data["admin_username"],
            email=data["admin_email"],
            password=data["admin_password"],
            tenant=tenant,
            is_staff=True,
            is_platform_admin=False,
        )
        return tenant
