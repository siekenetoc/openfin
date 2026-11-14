from __future__ import annotations

import logging
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from apps.banking.models import BankAccount, BankTransaction

from .fints_client import FintsError, TANRequired, get_fints_client

logger = logging.getLogger("openfin.banking.sync")


@transaction.atomic
def _upsert_transactions(account: BankAccount, txs) -> list[BankTransaction]:
    created: list[BankTransaction] = []
    for tx in txs:
        obj, was_created = BankTransaction.objects.update_or_create(
            account=account,
            external_id=tx.external_id,
            defaults={
                "booking_date": tx.booking_date,
                "value_date": tx.value_date,
                "amount": tx.amount,
                "currency": tx.currency or "EUR",
                "counterparty_name": tx.counterparty_name or "",
                "counterparty_iban": (tx.counterparty_iban or "").replace(" ", ""),
                "purpose": tx.purpose or "",
                "transaction_type": tx.transaction_type or "",
                "raw_data": tx.raw or {},
            },
        )
        if was_created:
            created.append(obj)
    return created


def sync_account(account: BankAccount, start: date | None = None, end: date | None = None, client=None) -> dict:
    end = end or date.today()
    start = start or (end - timedelta(days=90))
    client = client or get_fints_client(account)

    try:
        infos = client.fetch_accounts()
        for info in infos:
            if account.iban and info.iban and info.iban != account.iban:
                continue
            account.balance = info.balance
            account.balance_updated_at = timezone.now()
            if info.bic and not account.bic:
                account.bic = info.bic
            break

        txs = client.fetch_transactions(account, start, end)
        created = _upsert_transactions(account, txs)
        account.last_sync_at = timezone.now()
        account.sync_error = ""
        account.needs_tan = False
        account.save()

        reconciled = 0
        for tx in created:
            try:
                from apps.erp.reconciliation import reconcile_transaction

                result = reconcile_transaction(tx)
                if result.get("status") in {
                    BankTransaction.Status.AUTO_RECONCILED,
                    BankTransaction.Status.MATCHED,
                    BankTransaction.Status.NEEDS_REVIEW,
                }:
                    reconciled += 1
            except Exception:  # noqa: BLE001
                logger.exception("Reconciliation für Transaktion %s fehlgeschlagen", tx.pk)

        return {
            "status": "ok",
            "created": len(created),
            "total": len(txs),
            "reconciled": reconciled,
            "balance": str(account.balance),
        }
    except TANRequired as exc:
        from .tan import create_tan_challenge

        challenge = create_tan_challenge(account, "sync", exc)
        account.sync_error = "TAN-Freigabe erforderlich."
        account.save(update_fields=["sync_error"])
        return {
            "status": "pending_tan",
            "challenge_id": challenge.pk,
            "message": exc.challenge_text,
        }
    except FintsError as exc:
        account.sync_error = str(exc)
        account.last_sync_at = timezone.now()
        account.save(update_fields=["sync_error", "last_sync_at"])
        logger.warning("FinTS-Sync für Konto %s fehlgeschlagen: %s", account.pk, exc)
        return {"status": "error", "message": str(exc)}
    finally:
        close = getattr(client, "close", None)
        if close:
            close()
