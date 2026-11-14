from __future__ import annotations

from decimal import Decimal

from django.db import models

from apps.core.fields import EncryptedTextField


class ERPConfig(models.Model):
    name = models.CharField(max_length=120, default="ERPNext")
    erp_base_url = models.URLField()
    api_key = EncryptedTextField(blank=True)
    api_secret = EncryptedTextField(blank=True)
    webhook_secret = EncryptedTextField(blank=True)
    company = models.CharField(max_length=150, blank=True)
    default_currency = models.CharField(max_length=3, default="EUR")
    default_bank_account = models.ForeignKey(
        "banking.BankAccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="erp_configs",
    )
    transit_account_stripe = models.CharField(max_length=150, blank=True, default="Geldtransit Stripe")
    transit_account_paypal = models.CharField(max_length=150, blank=True, default="Geldtransit PayPal")
    transit_account_wero = models.CharField(max_length=150, blank=True, default="Geldtransit Wero")
    skonto_account = models.CharField(max_length=150, blank=True, default="Skontoaufwand")
    default_debit_account = models.CharField(max_length=150, blank=True, default="Bank")
    default_credit_account = models.CharField(max_length=150, blank=True, default="Debitoren")
    default_discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("2.00"))
    default_discount_days = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ERP-Konfiguration"
        verbose_name_plural = "ERP-Konfigurationen"

    def __str__(self) -> str:
        return f"{self.name} ({self.erp_base_url})"

    @property
    def has_credentials(self) -> bool:
        return bool(self.erp_base_url and self.api_key and self.api_secret)


class ExpectedPayment(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Offen"
        PAID = "paid", "Bezahlt"
        PARTIAL = "partial", "Teilzahlung"
        CANCELLED = "cancelled", "Storniert"

    erp_config = models.ForeignKey(
        ERPConfig,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expected_payments",
    )
    erp_name = models.CharField(max_length=120, blank=True, help_text="ERPNext Document Name")
    invoice_id = models.CharField(max_length=120, db_index=True)
    customer_name = models.CharField(max_length=200)
    customer_iban = models.CharField(max_length=34, blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    issue_date = models.DateField()
    due_date = models.DateField()
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("2.00"))
    discount_days = models.PositiveIntegerField(default=10)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_date", "invoice_id"]
        constraints = [
            models.UniqueConstraint(fields=["invoice_id"], name="erp_expected_unique_invoice"),
        ]
        indexes = [
            models.Index(fields=["status", "due_date"]),
        ]
        verbose_name = "Erwartete Zahlung"
        verbose_name_plural = "Erwartete Zahlungen"

    def __str__(self) -> str:
        return f"{self.invoice_id} – {self.customer_name} – {self.amount} {self.currency}"

    @property
    def discount_amount(self) -> Decimal:
        return (self.amount * self.discount_rate / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def discounted_amount(self) -> Decimal:
        return self.amount - self.discount_amount


class ReconciliationMatch(models.Model):
    class Stage(models.TextChoices):
        TRIGRAM = "stage1_trigram", "Stufe 1 – Regex + Trigram"
        SKONTO = "stage2_skonto", "Stufe 2 – Skonto/Rundung"
        SUBSET = "stage3_subset", "Stufe 3 – Sammelüberweisung"
        MANUAL = "manual", "Manuell"

    class Status(models.TextChoices):
        PROPOSED = "proposed", "Vorschlag"
        AUTO = "auto", "Automatisch verbucht"
        CONFIRMED = "confirmed", "Bestätigt"
        REJECTED = "rejected", "Verworfen"

    transaction = models.ForeignKey(
        "banking.BankTransaction",
        on_delete=models.CASCADE,
        related_name="reconciliation_matches",
    )
    expected_payment = models.ForeignKey(
        ExpectedPayment,
        on_delete=models.CASCADE,
        related_name="reconciliation_matches",
    )
    score = models.PositiveSmallIntegerField(default=0)
    stage = models.CharField(max_length=30, choices=Stage.choices, default=Stage.TRIGRAM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROPOSED)
    matched_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    deductions = models.JSONField(default=list, blank=True)
    references = models.JSONField(default=list, blank=True)
    erp_payment_entry = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["transaction", "expected_payment"], name="erp_match_unique_tx_payment"
            ),
        ]
        verbose_name = "Abgleich"
        verbose_name_plural = "Abgleiche"

    def __str__(self) -> str:
        return f"{self.transaction_id} ↔ {self.expected_payment.invoice_id} ({self.score}%)"


class PurchaseInvoice(models.Model):
    class Status(models.TextChoices):
        FETCHED = "fetched", "Abgerufen"
        QUEUED = "queued", "Im Ausgangskorb"
        PAID = "paid", "Bezahlt"
        FAILED = "failed", "Fehler"

    erp_config = models.ForeignKey(ERPConfig, null=True, blank=True, on_delete=models.SET_NULL)
    erp_name = models.CharField(max_length=120)
    invoice_id = models.CharField(max_length=120)
    supplier = models.CharField(max_length=200)
    supplier_iban = models.CharField(max_length=34, blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.FETCHED)
    outgoing_payment = models.ForeignKey(
        "banking.OutgoingPayment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_invoices",
    )
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["erp_name"], name="erp_purchase_unique_doc"),
        ]
        verbose_name = "Eingangsrechnung"
        verbose_name_plural = "Eingangsrechnungen"

    def __str__(self) -> str:
        return f"{self.invoice_id} – {self.supplier} – {self.amount}"
