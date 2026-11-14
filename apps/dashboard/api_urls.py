from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.banking.models import BankAccount, BankTransaction, OutgoingPayment
from apps.billing.models import PaymentLink, SEPAMandate, SepaBatch
from apps.erp.models import ExpectedPayment, ReconciliationMatch
from apps.providers.models import DepotPosition

from .serializers import (
    BankAccountSerializer,
    BankTransactionSerializer,
    DepotPositionSerializer,
    ExpectedPaymentSerializer,
    OutgoingPaymentSerializer,
    PaymentLinkSerializer,
    ReconciliationMatchSerializer,
    SEPAMandateSerializer,
    SepaBatchSerializer,
)

router = DefaultRouter()


class BankAccountViewSet(ReadOnlyModelViewSet):
    queryset = BankAccount.objects.all()
    serializer_class = BankAccountSerializer
    filterset_fields = ["account_type", "provider"]
    search_fields = ["name", "iban"]


class BankTransactionViewSet(ReadOnlyModelViewSet):
    queryset = BankTransaction.objects.select_related("account")
    serializer_class = BankTransactionSerializer
    filterset_fields = ["account", "status", "currency"]
    search_fields = ["purpose", "counterparty_name"]


class ExpectedPaymentViewSet(ReadOnlyModelViewSet):
    queryset = ExpectedPayment.objects.all()
    serializer_class = ExpectedPaymentSerializer
    filterset_fields = ["status", "currency"]
    search_fields = ["invoice_id", "customer_name"]


class ReconciliationMatchViewSet(ReadOnlyModelViewSet):
    queryset = ReconciliationMatch.objects.select_related("expected_payment")
    serializer_class = ReconciliationMatchSerializer
    filterset_fields = ["status", "stage"]


class SepaBatchViewSet(ReadOnlyModelViewSet):
    queryset = SepaBatch.objects.prefetch_related("items")
    serializer_class = SepaBatchSerializer
    filterset_fields = ["status"]


class MandateViewSet(ReadOnlyModelViewSet):
    queryset = SEPAMandate.objects.all()
    serializer_class = SEPAMandateSerializer
    filterset_fields = ["is_active", "mandate_type"]


class PaymentLinkViewSet(ReadOnlyModelViewSet):
    queryset = PaymentLink.objects.all()
    serializer_class = PaymentLinkSerializer
    filterset_fields = ["provider", "status"]


class OutgoingPaymentViewSet(ReadOnlyModelViewSet):
    queryset = OutgoingPayment.objects.all()
    serializer_class = OutgoingPaymentSerializer
    filterset_fields = ["status", "payment_type"]


class DepotPositionViewSet(ReadOnlyModelViewSet):
    queryset = DepotPosition.objects.all()
    serializer_class = DepotPositionSerializer
    filterset_fields = ["account"]


router.register("accounts", BankAccountViewSet, basename="api-bank-accounts")
router.register("transactions", BankTransactionViewSet, basename="api-transactions")
router.register("expected-payments", ExpectedPaymentViewSet, basename="api-expected")
router.register("matches", ReconciliationMatchViewSet, basename="api-matches")
router.register("sepa-batches", SepaBatchViewSet, basename="api-sepa-batches")
router.register("mandates", MandateViewSet, basename="api-mandates")
router.register("payment-links", PaymentLinkViewSet, basename="api-payment-links")
router.register("outgoing-payments", OutgoingPaymentViewSet, basename="api-outgoing-payments")
router.register("depot-positions", DepotPositionViewSet, basename="api-depot-positions")

urlpatterns = router.urls
