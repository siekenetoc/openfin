from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import models

from apps.core.fields import EncryptedTextField


class PaymentProviderConfig(models.Model):
    class Provider(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        PAYPAL = "paypal", "PayPal"
        WERO = "wero", "Wero (EPI)"

    provider = models.CharField(max_length=20, choices=Provider.choices)
    api_key = EncryptedTextField(blank=True)
    api_secret = EncryptedTextField(blank=True)
    webhook_secret = EncryptedTextField(blank=True)
    merchant_id = models.CharField(max_length=120, blank=True)
    mode = models.CharField(max_length=20, default="sandbox")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["provider"], name="billing_provider_unique"),
        ]
        verbose_name = "Payment-Provider-Konfiguration"
        verbose_name_plural = "Payment-Provider-Konfigurationen"

    def __str__(self) -> str:
        return f"{self.get_provider_display()} ({self.mode})"


class SEPAMandate(models.Model):
    class MandateType(models.TextChoices):
        CORE = "CORE", "Basislastschrift (CORE)"
        B2B = "B2B", "Firmenlastschrift (B2B)"

    class SequenceType(models.TextChoices):
        FRST = "FRST", "Erstlastschrift"
        RCUR = "RCUR", "Folgelastschrift"
        OOFF = "OOFF", "Einmallastschrift"
        FNAL = "FNAL", "Letztmalig"

    mandate_reference = models.CharField(max_length=35, unique=True)
    creditor_id = models.CharField(max_length=35)
    creditor_name = models.CharField(max_length=150)
    debtor_name = models.CharField(max_length=200)
    debtor_iban = models.CharField(max_length=34)
    debtor_bic = models.CharField(max_length=11, blank=True)
    debtor_email = models.EmailField(blank=True)
    customer_ref = models.CharField(max_length=120, blank=True)
    mandate_type = models.CharField(max_length=10, choices=MandateType.choices, default=MandateType.CORE)
    sequence_type = models.CharField(max_length=10, choices=SequenceType.choices, default=SequenceType.FRST)
    signature_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["debtor_name"]
        verbose_name = "SEPA-Mandat"
        verbose_name_plural = "SEPA-Mandate"

    def __str__(self) -> str:
        return f"{self.debtor_name} – {self.mandate_reference}"


class SepaBatch(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        XML_CREATED = "xml_created", "XML erzeugt"
        SUBMITTED = "submitted", "Eingereicht"
        EXECUTED = "executed", "Ausgeführt"
        FAILED = "failed", "Fehlgeschlagen"

    batch_id = models.CharField(max_length=60, unique=True, editable=False)
    account = models.ForeignKey("banking.BankAccount", on_delete=models.PROTECT, related_name="sepa_batches")
    collection_date = models.DateField()
    description = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    total_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    xml_file = models.TextField(blank=True)
    message_id = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "SEPA-Batch"
        verbose_name_plural = "SEPA-Batches"

    def __str__(self) -> str:
        return f"{self.batch_id} – {self.total_amount} EUR"

    def save(self, *args, **kwargs):
        if not self.batch_id:
            self.batch_id = f"SEPA-{uuid.uuid4().hex[:12].upper()}"
        if not self.message_id:
            self.message_id = f"MSG-{uuid.uuid4().hex[:16].upper()}"
        super().save(*args, **kwargs)

    def recalculate(self) -> None:
        total = sum((item.amount for item in self.items.all()), Decimal("0.00"))
        self.total_amount = total
        self.save(update_fields=["total_amount"])


class SepaBatchItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Offen"
        PRENOTIFIED = "prenotified", "Vorab angekündigt"
        COLLECTED = "collected", "Eingezogen"
        RETURNED = "returned", "Rückgabe"
        FAILED = "failed", "Fehlgeschlagen"

    batch = models.ForeignKey(SepaBatch, on_delete=models.CASCADE, related_name="items")
    mandate = models.ForeignKey(SEPAMandate, on_delete=models.PROTECT, related_name="batch_items")
    expected_payment = models.ForeignKey(
        "erp.ExpectedPayment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sepa_items",
    )
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    purpose = models.CharField(max_length=140)
    end_to_end_id = models.CharField(max_length=35, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    prenotified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "SEPA-Einzug"
        verbose_name_plural = "SEPA-Einzüge"

    def __str__(self) -> str:
        return f"{self.mandate.debtor_name} – {self.amount}"

    def save(self, *args, **kwargs):
        if not self.end_to_end_id:
            self.end_to_end_id = f"E2E-{uuid.uuid4().hex[:20].upper()}"
        super().save(*args, **kwargs)


class PaymentLink(models.Model):
    class Provider(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        PAYPAL = "paypal", "PayPal"
        WERO = "wero", "Wero"

    class Status(models.TextChoices):
        CREATED = "created", "Erzeugt"
        SENT = "sent", "Versendet"
        PAID = "paid", "Bezahlt"
        EXPIRED = "expired", "Abgelaufen"
        CANCELLED = "cancelled", "Storniert"

    provider = models.CharField(max_length=20, choices=Provider.choices)
    expected_payment = models.ForeignKey(
        "erp.ExpectedPayment",
        on_delete=models.CASCADE,
        related_name="payment_links",
    )
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    url = models.URLField(max_length=500)
    qr_code = models.TextField(blank=True, help_text="Data-URI eines lokal erzeugten QR-Codes.")
    external_id = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payment-Link"
        verbose_name_plural = "Payment-Links"

    def __str__(self) -> str:
        return f"{self.get_provider_display()} – {self.amount} {self.currency}"


class PaymentEvent(models.Model):
    provider = models.CharField(max_length=20)
    event_id = models.CharField(max_length=160, unique=True)
    event_type = models.CharField(max_length=80, blank=True)
    payload = models.JSONField(default=dict)
    signature_valid = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    external_ref = models.CharField(max_length=160, blank=True)
    expected_payment = models.ForeignKey(
        "erp.ExpectedPayment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payment-Webhook-Event"
        verbose_name_plural = "Payment-Webhook-Events"

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_id}"
