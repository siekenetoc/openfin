from django import forms

from apps.banking.models import BankAccount

from .models import PaymentProviderConfig, SEPAMandate, SepaBatch


class SEPAMandateForm(forms.ModelForm):
    class Meta:
        model = SEPAMandate
        fields = [
            "mandate_reference",
            "creditor_id",
            "creditor_name",
            "debtor_name",
            "debtor_iban",
            "debtor_bic",
            "debtor_email",
            "customer_ref",
            "mandate_type",
            "sequence_type",
            "signature_date",
            "is_active",
        ]
        widgets = {"signature_date": forms.DateInput(attrs={"type": "date"})}


class SepaBatchCreateForm(forms.Form):
    account = forms.ModelChoiceField(queryset=BankAccount.objects.none(), label="Auftragskonto")
    collection_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), label="Einzugsdatum")
    description = forms.CharField(max_length=200, required=False, label="Beschreibung")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = BankAccount.objects.filter(is_active=True).exclude(iban="")


class PaymentProviderConfigForm(forms.ModelForm):
    class Meta:
        model = PaymentProviderConfig
        fields = ["provider", "api_key", "api_secret", "webhook_secret", "merchant_id", "mode", "is_active"]
        widgets = {
            "api_key": forms.PasswordInput(render_value=True),
            "api_secret": forms.PasswordInput(render_value=True),
            "webhook_secret": forms.PasswordInput(render_value=True),
        }


class BatchSelectionForm(forms.Form):
    payment_ids = forms.ModelMultipleChoiceField(queryset=None, required=True)

    def __init__(self, *args, **kwargs):
        from apps.erp.models import ExpectedPayment

        super().__init__(*args, **kwargs)
        self.fields["payment_ids"].queryset = ExpectedPayment.objects.filter(
            status=ExpectedPayment.Status.OPEN
        )
