from __future__ import annotations

from decimal import Decimal

from django.db import models


class DepotPosition(models.Model):
    account = models.ForeignKey(
        "banking.BankAccount",
        on_delete=models.CASCADE,
        related_name="depot_positions",
    )
    isin = models.CharField(max_length=12, db_index=True)
    name = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal("0.000000"))
    price = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal("0.0000"))
    currency = models.CharField(max_length=3, default="EUR")
    yahoo_symbol = models.CharField(max_length=30, blank=True)
    price_source = models.CharField(max_length=80, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["account", "isin"], name="providers_depot_unique_isin"),
        ]
        verbose_name = "Depotposition"
        verbose_name_plural = "Depotpositionen"

    def __str__(self) -> str:
        return f"{self.name} ({self.isin})"

    @property
    def market_value(self) -> Decimal:
        return (self.quantity * self.price).quantize(Decimal("0.01"))


class ScrapeRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ausstehend"
        RUNNING = "running", "Läuft"
        SUCCESS = "success", "Erfolgreich"
        FAILED = "failed", "Fehlgeschlagen"

    account = models.ForeignKey(
        "banking.BankAccount",
        on_delete=models.CASCADE,
        related_name="scrape_runs",
    )
    scraper = models.CharField(max_length=60, default="amazon")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    items_found = models.PositiveIntegerField(default=0)
    documents_saved = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Scrape-Lauf"
        verbose_name_plural = "Scrape-Läufe"

    def __str__(self) -> str:
        return f"{self.scraper} – {self.account} – {self.status}"
