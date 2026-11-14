from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.banking.models import BankAccount
from apps.billing.models import PaymentProviderConfig
from apps.erp.models import ERPConfig
from apps.integrations.models import DATEVConfig


class Command(BaseCommand):
    help = "Re-verschlüsselt alle Secret-Felder mit dem aktuellen FIELD_ENCRYPTION_KEY."

    @transaction.atomic
    def handle(self, *args, **options):
        count = 0
        for account in BankAccount.objects.all():
            account.fints_pin = account.fints_pin
            account.credentials = account.credentials
            account.save(update_fields=["fints_pin", "credentials"])
            count += 1
        for config in ERPConfig.objects.all():
            config.api_key = config.api_key
            config.api_secret = config.api_secret
            config.webhook_secret = config.webhook_secret
            config.save(update_fields=["api_key", "api_secret", "webhook_secret"])
            count += 1
        for config in PaymentProviderConfig.objects.all():
            config.api_key = config.api_key
            config.api_secret = config.api_secret
            config.webhook_secret = config.webhook_secret
            config.save(update_fields=["api_key", "api_secret", "webhook_secret"])
            count += 1
        for config in DATEVConfig.objects.all():
            config.oauth_client_id = config.oauth_client_id
            config.oauth_client_secret = config.oauth_client_secret
            config.oauth_refresh_token = config.oauth_refresh_token
            config.save(update_fields=["oauth_client_id", "oauth_client_secret", "oauth_refresh_token"])
            count += 1
        self.stdout.write(self.style.SUCCESS(f"{count} Datensätze re-verschlüsselt."))
