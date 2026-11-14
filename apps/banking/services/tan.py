from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.banking.models import TANChallenge

from .fints_client import FintsError, TANRequired, get_fints_client

logger = logging.getLogger("openfin.tan")


def _cache_key(challenge_id: int) -> str:
    return f"openfin:tan:{challenge_id}"


def create_tan_challenge(account, operation: str, exc: TANRequired, payload: dict | None = None) -> TANChallenge:
    ttl = getattr(settings, "FINTS_TAN_STATE_TTL_SECONDS", 900)
    challenge = TANChallenge.objects.create(
        account=account,
        operation=operation,
        tan_type=exc.tan_type or TANChallenge.TANType.PUSH,
        challenge_text=exc.challenge_text,
        challenge_image=exc.challenge_image,
        dialog_state=exc.dialog_state,
        payload={**(payload or {}), **(exc.payload or {})},
        expires_at=timezone.now() + timedelta(seconds=ttl),
    )
    try:
        cache.set(_cache_key(challenge.pk), {"dialog_state": exc.dialog_state}, timeout=ttl)
    except Exception as cache_exc:  # noqa: BLE001
        logger.warning("TAN-State konnte nicht in Redis gespeichert werden: %s", cache_exc)
    account.needs_tan = True
    account.save(update_fields=["needs_tan"])
    return challenge


def cached_dialog_state(challenge: TANChallenge) -> str:
    try:
        cached = cache.get(_cache_key(challenge.pk))
        if cached and cached.get("dialog_state"):
            return cached["dialog_state"]
    except Exception:  # noqa: BLE001
        pass
    return challenge.dialog_state


def expire_challenge(challenge: TANChallenge, message: str = "TAN-Freigabe abgelaufen.") -> TANChallenge:
    challenge.status = TANChallenge.Status.EXPIRED
    challenge.error_message = message
    challenge.completed_at = timezone.now()
    challenge.save(update_fields=["status", "error_message", "completed_at"])
    try:
        cache.delete(_cache_key(challenge.pk))
    except Exception:  # noqa: BLE001
        pass
    challenge.account.needs_tan = False
    challenge.account.save(update_fields=["needs_tan"])
    return challenge


def confirm_tan_challenge(challenge: TANChallenge, response: str) -> TANChallenge:
    if challenge.status != TANChallenge.Status.PENDING:
        return challenge
    if challenge.is_expired:
        return expire_challenge(challenge)

    dialog_state = cached_dialog_state(challenge)
    try:
        if settings.FINTS_USE_MOCK:
            from .fints_client import MockFinTSClient

            result = MockFinTSClient().confirm_tan(challenge, response)
        else:
            client = get_fints_client(challenge.account, from_data=dialog_state)
            result = client.confirm_tan(challenge, response)
        challenge.status = TANChallenge.Status.CONFIRMED
        challenge.completed_at = timezone.now()
        challenge.payload = {**(challenge.payload or {}), "result": result.__dict__}
        challenge.save(update_fields=["status", "completed_at", "payload"])
        challenge.account.needs_tan = False
        challenge.account.save(update_fields=["needs_tan"])
        _apply_operation(challenge)
    except (FintsError, Exception) as exc:  # noqa: BLE001
        logger.exception("TAN-Bestätigung fehlgeschlagen")
        challenge.status = TANChallenge.Status.FAILED
        challenge.error_message = str(exc)
        challenge.completed_at = timezone.now()
        challenge.save(update_fields=["status", "error_message", "completed_at"])
        challenge.account.needs_tan = False
        challenge.account.save(update_fields=["needs_tan"])
    finally:
        try:
            cache.delete(_cache_key(challenge.pk))
        except Exception:  # noqa: BLE001
            pass
    return challenge


def _apply_operation(challenge: TANChallenge) -> None:
    payload = challenge.payload or {}
    if challenge.operation == "payment" and payload.get("payment_id"):
        from apps.banking.models import OutgoingPayment

        payment = OutgoingPayment.objects.filter(pk=payload["payment_id"], account=challenge.account).first()
        if payment:
            payment.status = OutgoingPayment.Status.SUBMITTED
            payment.tan_challenge = challenge
            payment.save(update_fields=["status", "tan_challenge"])
    elif challenge.operation == "sync":
        from .sync import sync_account

        sync_account(challenge.account)
