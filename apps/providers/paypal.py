from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.banking.models import BankAccount, BankTransaction

logger = logging.getLogger("openfin.paypal")


class PayPalError(RuntimeError):
    pass


class PayPalRESTClient:
    def __init__(self, account: BankAccount):
        credentials = account.credentials or {}
        self.client_id = credentials.get("client_id") or settings.PAYPAL_CLIENT_ID
        self.client_secret = credentials.get("client_secret") or settings.PAYPAL_CLIENT_SECRET
        self.mode = credentials.get("mode") or settings.PAYPAL_MODE
        self.base_url = (
            "https://api-m.paypal.com" if self.mode == "live" else "https://api-m.sandbox.paypal.com"
        )
        self.session = requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _token(self) -> str:
        if not self.configured:
            raise PayPalError("PayPal Client-ID/Secret fehlen.")
        response = self.session.post(
            f"{self.base_url}/v1/oauth2/token",
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            timeout=20,
        )
        if response.status_code >= 400:
            raise PayPalError(f"PayPal OAuth fehlgeschlagen: {response.status_code} {response.text[:300]}")
        return response.json()["access_token"]

    def list_transactions(self, start: date, end: date, page_size: int = 100) -> list[dict]:
        token = self._token()
        transactions: list[dict] = []
        page = 1
        while True:
            response = self.session.get(
                f"{self.base_url}/v1/reporting/transactions",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                params={
                    "start_date": start.strftime("%Y-%m-%dT00:00:00Z"),
                    "end_date": end.strftime("%Y-%m-%dT23:59:59Z"),
                    "page_size": page_size,
                    "page": page,
                    "fields": "all",
                },
                timeout=30,
            )
            if response.status_code >= 400:
                raise PayPalError(f"PayPal Transaktionen: {response.status_code} {response.text[:300]}")
            data = response.json()
            batch = data.get("transaction_details", [])
            transactions.extend(batch)
            total_pages = data.get("total_pages", 1)
            if page >= total_pages or not batch:
                break
            page += 1
        return transactions

    def list_balances(self) -> list[dict]:
        token = self._token()
        response = self.session.get(
            f"{self.base_url}/v1/reporting/balances",
            headers={"Authorization": f"Bearer {token}"},
            params={"currency_code": "EUR"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json().get("balances", [])


@transaction.atomic
def sync_paypal_account(account: BankAccount, start: date | None = None, end: date | None = None) -> dict:
    end = end or date.today()
    start = start or (end - timedelta(days=90))
    client = PayPalRESTClient(account)
    if not client.configured:
        return {"status": "skipped", "reason": "PayPal ist nicht konfiguriert."}
    transactions = client.list_transactions(start, end)
    created = 0
    for entry in transactions:
        info = entry.get("transaction_info", {})
        amount_data = info.get("transaction_amount", {})
        try:
            amount = Decimal(str(amount_data.get("value", "0")))
        except Exception:  # noqa: BLE001
            continue
        event_date = info.get("transaction_initiation_date") or info.get("transaction_updated_date")
        try:
            booking_date = datetime.strptime(event_date[:10], "%Y-%m-%d").date()
        except Exception:  # noqa: BLE001
            booking_date = end
        payer = entry.get("payer_info", {})
        external_id = info.get("transaction_id") or f"paypal-{account.pk}-{created}"
        _, was_created = BankTransaction.objects.update_or_create(
            account=account,
            external_id=str(external_id),
            defaults={
                "booking_date": booking_date,
                "value_date": booking_date,
                "amount": amount,
                "currency": amount_data.get("currency_code", "EUR"),
                "counterparty_name": payer.get("payer_name", {}).get("alternate_full_name", ""),
                "purpose": info.get("transaction_subject", "")
                or info.get("transaction_note", "")
                or info.get("transaction_event_code", ""),
                "transaction_type": info.get("transaction_event_code", ""),
                "raw_data": {k: str(v) for k, v in info.items()},
            },
        )
        if was_created:
            created += 1
    balances = client.list_balances()
    if balances:
        account.balance = Decimal(str(balances[0].get("available_balance", {}).get("value", account.balance)))
        account.balance_updated_at = timezone.now()
    account.last_sync_at = timezone.now()
    account.save()
    return {"status": "ok", "fetched": len(transactions), "created": created}
