from rest_framework import serializers

from apps.banking.models import BankAccount, BankTransaction, OutgoingPayment
from apps.billing.models import PaymentLink, SEPAMandate, SepaBatch, SepaBatchItem
from apps.erp.models import ExpectedPayment, ReconciliationMatch
from apps.providers.models import DepotPosition


class BankAccountSerializer(serializers.ModelSerializer):
    masked_iban = serializers.ReadOnlyField()

    class Meta:
        model = BankAccount
        fields = [
            "id",
            "name",
            "account_type",
            "provider",
            "bank_name",
            "holder",
            "iban",
            "masked_iban",
            "bic",
            "currency",
            "balance",
            "needs_tan",
            "last_sync_at",
        ]


class BankTransactionSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = BankTransaction
        fields = [
            "id",
            "account",
            "account_name",
            "booking_date",
            "value_date",
            "amount",
            "currency",
            "counterparty_name",
            "counterparty_iban",
            "purpose",
            "category",
            "cost_center",
            "status",
            "confidence_score",
            "paperless_document_id",
        ]


class ExpectedPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpectedPayment
        fields = [
            "id",
            "invoice_id",
            "erp_name",
            "customer_name",
            "customer_iban",
            "amount",
            "currency",
            "issue_date",
            "due_date",
            "status",
            "discount_rate",
            "discount_days",
        ]


class ReconciliationMatchSerializer(serializers.ModelSerializer):
    invoice_id = serializers.CharField(source="expected_payment.invoice_id", read_only=True)

    class Meta:
        model = ReconciliationMatch
        fields = [
            "id",
            "transaction",
            "expected_payment",
            "invoice_id",
            "score",
            "stage",
            "status",
            "matched_amount",
            "discount_amount",
            "erp_payment_entry",
        ]


class SepaBatchItemSerializer(serializers.ModelSerializer):
    debtor = serializers.CharField(source="mandate.debtor_name", read_only=True)

    class Meta:
        model = SepaBatchItem
        fields = ["id", "mandate", "debtor", "amount", "purpose", "status", "end_to_end_id"]


class SepaBatchSerializer(serializers.ModelSerializer):
    items = SepaBatchItemSerializer(many=True, read_only=True)

    class Meta:
        model = SepaBatch
        fields = ["id", "batch_id", "account", "collection_date", "status", "total_amount", "items"]


class SEPAMandateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SEPAMandate
        fields = [
            "id",
            "mandate_reference",
            "creditor_id",
            "debtor_name",
            "debtor_iban",
            "debtor_bic",
            "mandate_type",
            "sequence_type",
            "signature_date",
            "is_active",
        ]


class PaymentLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentLink
        fields = ["id", "provider", "expected_payment", "amount", "currency", "url", "status", "created_at"]


class OutgoingPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutgoingPayment
        fields = [
            "id",
            "account",
            "payment_type",
            "recipient_name",
            "recipient_iban",
            "amount",
            "currency",
            "purpose",
            "status",
            "created_at",
        ]


class DepotPositionSerializer(serializers.ModelSerializer):
    market_value = serializers.ReadOnlyField()

    class Meta:
        model = DepotPosition
        fields = [
            "id",
            "account",
            "isin",
            "name",
            "quantity",
            "price",
            "currency",
            "market_value",
            "updated_at",
        ]
