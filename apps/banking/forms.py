from __future__ import annotations

from django import forms

from .models import BankAccount, OutgoingPayment, StandingOrder


class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = [
            "name",
            "account_type",
            "provider",
            "bank_name",
            "holder",
            "iban",
            "bic",
            "currency",
            "fints_blz",
            "fints_login",
            "fints_endpoint",
            "fints_pin",
            "fints_product_id",
            "credentials",
            "is_active",
        ]
        widgets = {
            "fints_pin": forms.PasswordInput(render_value=True),
            "credentials": forms.Textarea(attrs={"rows": 4, "placeholder": '{"client_id": "…"}'}),
        }

    def clean_iban(self):
        return (self.cleaned_data.get("iban") or "").replace(" ", "").upper()

    def clean_fints_pin(self):
        pin = self.cleaned_data.get("fints_pin")
        if pin and self.instance.pk:
            # Unveränderte Maskierung nicht erneut speichern.
            if pin == "********":
                return self.instance.fints_pin
        return pin


class OutgoingPaymentForm(forms.ModelForm):
    class Meta:
        model = OutgoingPayment
        fields = [
            "account",
            "payment_type",
            "recipient_name",
            "recipient_iban",
            "recipient_bic",
            "amount",
            "currency",
            "purpose",
            "execution_date",
        ]
        widgets = {
            "execution_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = BankAccount.objects.filter(is_active=True)
        self.fields["recipient_iban"].widget.attrs.update({"placeholder": "DE…"})

    def clean_recipient_iban(self):
        return (self.cleaned_data.get("recipient_iban") or "").replace(" ", "").upper()


class StandingOrderForm(forms.ModelForm):
    class Meta:
        model = StandingOrder
        fields = [
            "account",
            "recipient_name",
            "recipient_iban",
            "recipient_bic",
            "amount",
            "currency",
            "purpose",
            "interval",
            "start_date",
            "end_date",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = BankAccount.objects.filter(is_active=True)


class TransactionFilterForm(forms.Form):
    account = forms.ModelChoiceField(queryset=BankAccount.objects.none(), required=False, empty_label="Alle Konten")
    status = forms.ChoiceField(
        choices=[("", "Alle Status")] + list(
            [
                ("unmatched", "Unzugeordnet"),
                ("needs_review", "Prüfung nötig"),
                ("auto_reconciled", "Automatisch verbucht"),
                ("matched", "Manuell verbucht"),
                ("ignored", "Ignoriert"),
            ]
        ),
        required=False,
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    search = forms.CharField(required=False, label="Suche")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = BankAccount.objects.filter(is_active=True)
