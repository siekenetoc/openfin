from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.fields import EncryptedJSONField, EncryptedTextField


class BankAccount(models.Model):
    class AccountType(models.TextChoices):
        GIRO = "giro", "Girokonto"
        TAGESGELD = "tagesgeld", "Tagesgeldkonto"
        FESTGELD = "festgeld", "Festgeldkonto"
        KREDITKARTE = "kreditkarte", "Kreditkarte"
        DEPOT = "depot", "Wertpapierdepot"
        WALLET = "wallet", "Wallet / E-Commerce"
        OFFLINE = "offline", "Offline / Barkasse"

    class Provider(models.TextChoices):
        FINTS = "fints", "FinTS / HBCI"
        PLAYWRIGHT = "playwright", "Playwright-Scraper"
        PAYPAL = "paypal", "PayPal REST"
        MANUAL = "manual", "Manuell / Offline"

    name = models.CharField(max_length=150)
    account_type = models.CharField(max_length=20, choices=AccountType.choices, default=AccountType.GIRO)
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.FINTS)
    bank_name = models.CharField(max_length=150, blank=True)
    holder = models.CharField(max_length=150, blank=True)
    iban = models.CharField(max_length=34, blank=True, db_index=True)
    bic = models.CharField(max_length=11, blank=True)
    currency = models.CharField(max_length=3, default="EUR")
    balance = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    balance_updated_at = models.DateTimeField(null=True, blank=True)

    fints_blz = models.CharField(max_length=8, blank=True, verbose_name="BLZ")
    fints_login = models.CharField(max_length=100, blank=True, verbose_name="FinTS-Login")
    fints_endpoint = models.URLField(blank=True, verbose_name="FinTS-Endpoint")
    fints_pin = EncryptedTextField(blank=True, verbose_name="FinTS-PIN (verschlüsselt)")
    fints_product_id = models.CharField(max_length=64, blank=True)
    credentials = EncryptedJSONField(default=dict, blank=True, help_text="Provider-Secrets (verschlüsselt).")

    needs_tan = models.BooleanField(default=False)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Bankkonto"
        verbose_name_plural = "Bankkonten"

    def __str__(self) -> str:
        return f"{self.name} ({self.get_account_type_display()})"

    @property
    def masked_iban(self) -> str:
        if not self.iban:
            return "—"
        return f"{self.iban[:4]} •••• {self.iban[-4:]}"

    @property
    def is_fints(self) -> bool:
        return self.provider == self.Provider.FINTS


class BankTransaction(models.Model):
    class Status(models.TextChoices):
        UNMATCHED = "unmatched", "Unzugeordnet"
        NEEDS_REVIEW = "needs_review", "Prüfung nötig"
        AUTO_RECONCILED = "auto_reconciled", "Automatisch verbucht"
        MATCHED = "matched", "Manuell verbucht"
        IGNORED = "ignored", "Ignoriert"

    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="transactions")
    external_id = models.CharField(max_length=120)
    booking_date = models.DateField()
    value_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    counterparty_name = models.CharField(max_length=200, blank=True)
    counterparty_iban = models.CharField(max_length=34, blank=True, db_index=True)
    purpose = models.TextField(blank=True)
    transaction_type = models.CharField(max_length=80, blank=True)
    category = models.CharField(max_length=120, blank=True)
    cost_center = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNMATCHED, db_index=True)
    confidence_score = models.PositiveSmallIntegerField(default=0)
    erp_payment_reference = models.CharField(max_length=120, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    paperless_document_id = models.CharField(max_length=64, blank=True)
    linked_document_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-booking_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["account", "external_id"], name="bank_tx_account_external"),
        ]
        indexes = [
            models.Index(fields=["booking_date"]),
            models.Index(fields=["status", "booking_date"]),
        ]
        verbose_name = "Bankumsatz"
        verbose_name_plural = "Bankumsätze"

    def __str__(self) -> str:
        return f"{self.booking_date} {self.amount} {self.counterparty_name}"

    @property
    def is_credit(self) -> bool:
        return self.amount > 0


class BankPartner(models.Model):
    name = models.CharField(max_length=200)
    iban = models.CharField(max_length=34, db_index=True)
    bic = models.CharField(max_length=11, blank=True)
    email = models.EmailField(blank=True)
    customer_ref = models.CharField(max_length=120, blank=True, help_text="ERPNext Customer / Debitorennummer")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["iban"], name="bank_partner_unique_iban"),
        ]
        verbose_name = "Geschäftspartner"
        verbose_name_plural = "Geschäftspartner"

    def __str__(self) -> str:
        return self.name


class CategoryRule(models.Model):
    name = models.CharField(max_length=120)
    pattern = models.CharField(max_length=300, help_text="Regex auf Verwendungszweck/Gegenpartei.")
    category = models.CharField(max_length=120)
    cost_center = models.CharField(max_length=120, blank=True)
    priority = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["priority", "name"]
        verbose_name = "Kategorisierungsregel"
        verbose_name_plural = "Kategorisierungsregeln"

    def __str__(self) -> str:
        return f"{self.name} → {self.category}"

    def matches(self, text: str) -> bool:
        import re

        try:
            return bool(re.search(self.pattern, text or "", re.IGNORECASE))
        except re.error:
            return False


class TANChallenge(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Offen"
        CONFIRMED = "confirmed", "Bestätigt"
        EXPIRED = "expired", "Abgelaufen"
        FAILED = "failed", "Fehlgeschlagen"
        CANCELLED = "cancelled", "Abgebrochen"

    class TANType(models.TextChoices):
        PUSH = "push_tan", "PushTAN"
        DECOUPLED = "decoupled", "Decoupled TAN"
        CHIP = "chip_tan", "chipTAN"
        PHOTO = "photo_tan", "photoTAN"
        MOBILE = "mobile_tan", "mobileTAN"

    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="tan_challenges")
    operation = models.CharField(max_length=40, default="sync")
    tan_type = models.CharField(max_length=20, choices=TANType.choices, default=TANType.PUSH)
    challenge_text = models.TextField(blank=True)
    challenge_image = models.TextField(blank=True, help_text="Data-URI (Flicker-/Matrix-Code).")
    dialog_state = EncryptedTextField(blank=True)
    payload = EncryptedJSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "TAN-Freigabe"
        verbose_name_plural = "TAN-Freigaben"

    def __str__(self) -> str:
        return f"TAN {self.get_tan_type_display()} für {self.account} ({self.status})"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at


class OutgoingPayment(models.Model):
    class PaymentType(models.TextChoices):
        SINGLE = "single", "Einzelüberweisung"
        COLLECTIVE = "collective", "Sammelüberweisung"
        INSTANT = "instant", "Echtzeitüberweisung"
        SCHEDULED = "scheduled", "Terminüberweisung"
        STANDING_ORDER = "standing_order", "Dauerauftrag"

    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        PENDING_TAN = "pending_tan", "TAN erforderlich"
        SUBMITTED = "submitted", "Eingereicht"
        EXECUTED = "executed", "Ausgeführt"
        FAILED = "failed", "Fehlgeschlagen"
        CANCELLED = "cancelled", "Storniert"

    account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="outgoing_payments")
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices, default=PaymentType.SINGLE)
    recipient_name = models.CharField(max_length=200)
    recipient_iban = models.CharField(max_length=34)
    recipient_bic = models.CharField(max_length=11, blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    currency = models.CharField(max_length=3, default="EUR")
    purpose = models.CharField(max_length=140, blank=True)
    execution_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    pain_xml = models.TextField(blank=True)
    reference = models.CharField(max_length=120, blank=True)
    tan_challenge = models.ForeignKey(
        TANChallenge, null=True, blank=True, on_delete=models.SET_NULL, related_name="payments"
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Ausgangszahlung"
        verbose_name_plural = "Ausgangszahlungen"

    def __str__(self) -> str:
        return f"{self.amount} {self.currency} an {self.recipient_name}"


class StandingOrder(models.Model):
    class Interval(models.TextChoices):
        WEEKLY = "weekly", "wöchentlich"
        MONTHLY = "monthly", "monatlich"
        QUARTERLY = "quarterly", "quartalsweise"
        YEARLY = "yearly", "jährlich"

    class Action(models.TextChoices):
        CREATE = "create", "Anlegen"
        UPDATE = "update", "Ändern"
        DELETE = "delete", "Löschen"

    account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="standing_orders")
    recipient_name = models.CharField(max_length=200)
    recipient_iban = models.CharField(max_length=34)
    recipient_bic = models.CharField(max_length=11, blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    purpose = models.CharField(max_length=140, blank=True)
    interval = models.CharField(max_length=20, choices=Interval.choices, default=Interval.MONTHLY)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    pending_action = models.CharField(max_length=10, choices=Action.choices, blank=True)
    external_id = models.CharField(max_length=120, blank=True)
    last_execution_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["recipient_name"]
        verbose_name = "Dauerauftrag"
        verbose_name_plural = "Daueraufträge"

    def __str__(self) -> str:
        return f"{self.recipient_name} – {self.amount} {self.interval}"


def new_external_id(prefix: str = "manual") -> str:
    return f"{prefix}-{uuid.uuid4().hex}"
