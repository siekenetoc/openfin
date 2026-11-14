from __future__ import annotations

from django.db import models

from apps.core.fields import EncryptedTextField


class DATEVConfig(models.Model):
    advisor_number = models.CharField(max_length=20, verbose_name="Beraternummer")
    client_number = models.CharField(max_length=20, verbose_name="Mandantennummer")
    fiscal_year = models.PositiveIntegerField(default=2026)
    account_length = models.PositiveSmallIntegerField(default=4)
    skr = models.CharField(max_length=2, default="03", verbose_name="SKR")
    default_debit_account = models.CharField(max_length=20, default="1200")
    default_credit_account = models.CharField(max_length=20, default="10000")
    oauth_client_id = EncryptedTextField(blank=True)
    oauth_client_secret = EncryptedTextField(blank=True)
    oauth_refresh_token = EncryptedTextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "DATEV-Konfiguration"
        verbose_name_plural = "DATEV-Konfigurationen"

    def __str__(self) -> str:
        return f"DATEV {self.advisor_number}/{self.client_number}"


class PaperlessDocumentLink(models.Model):
    transaction = models.ForeignKey(
        "banking.BankTransaction",
        on_delete=models.CASCADE,
        related_name="document_links",
    )
    document_id = models.CharField(max_length=64)
    title = models.CharField(max_length=300, blank=True)
    url = models.URLField(blank=True)
    match_score = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["transaction", "document_id"], name="integrations_paperless_unique"),
        ]
        verbose_name = "Paperless-Beleglink"
        verbose_name_plural = "Paperless-Beleglinks"


class AICategorization(models.Model):
    transaction = models.ForeignKey(
        "banking.BankTransaction",
        on_delete=models.CASCADE,
        related_name="ai_categorizations",
    )
    model = models.CharField(max_length=120)
    category = models.CharField(max_length=120)
    cost_center = models.CharField(max_length=120, blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    raw_response = models.JSONField(default=dict, blank=True)
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "KI-Kategorisierung"
        verbose_name_plural = "KI-Kategorisierungen"


class AIQuery(models.Model):
    question = models.TextField()
    generated_sql = models.TextField(blank=True)
    row_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "KI-Finanzabfrage"
        verbose_name_plural = "KI-Finanzabfragen"
