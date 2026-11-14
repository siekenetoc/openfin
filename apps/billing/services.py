from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.erp.client import ERPNextClient
from apps.erp.models import ERPConfig, ExpectedPayment, ReconciliationMatch
from apps.erp.services import active_config

from .gateways import create_gateway_link
from .models import (
    PaymentEvent,
    PaymentLink,
    PaymentProviderConfig,
    SEPAMandate,
    SepaBatch,
    SepaBatchItem,
)
from .sepa import build_pain008

logger = logging.getLogger("openfin.billing")


def create_payment_link(expected_payment: ExpectedPayment, provider: str, base_url: str = "") -> PaymentLink:
    existing = expected_payment.payment_links.filter(
        provider=provider, status__in=[PaymentLink.Status.CREATED, PaymentLink.Status.SENT]
    ).first()
    if existing:
        return existing
    gateway = create_gateway_link(expected_payment, provider, base_url)
    return PaymentLink.objects.create(
        provider=provider,
        expected_payment=expected_payment,
        amount=expected_payment.amount,
        currency=expected_payment.currency,
        url=gateway.url,
        qr_code=gateway.qr_code,
        external_id=gateway.external_id,
        metadata=gateway.metadata or {},
    )


def create_sepa_batch(account, collection_date: date, rows: list[dict], description: str = "") -> SepaBatch:
    batch = SepaBatch.objects.create(
        account=account,
        collection_date=collection_date,
        description=description,
        status=SepaBatch.Status.DRAFT,
    )
    for row in rows:
        SepaBatchItem.objects.create(
            batch=batch,
            mandate=row["mandate"],
            expected_payment=row.get("expected_payment"),
            amount=row["amount"],
            purpose=row.get("purpose", ""),
        )
    batch.recalculate()
    batch.xml_file = build_pain008(batch)
    batch.status = SepaBatch.Status.XML_CREATED
    batch.save(update_fields=["xml_file", "status", "total_amount"])
    return batch


def send_prenotification(item: SepaBatchItem) -> bool:
    mandate = item.mandate
    if not mandate.debtor_email:
        return False
    due = item.batch.collection_date
    subject = f"Vorabankündigung SEPA-Lastschrift {mandate.mandate_reference}"
    body = (
        f"Sehr geehrte Damen und Herren,\n\n"
        f"wir kündigen hiermit die SEPA-Lastschrift über {item.amount} EUR "
        f"(Rechnung {getattr(item.expected_payment, 'invoice_id', item.purpose)}) "
        f"zum {due.strftime('%d.%m.%Y')} an.\n\n"
        f"Mandatsreferenz: {mandate.mandate_reference}\n"
        f"Gläubiger-ID: {mandate.creditor_id}\n\n"
        f"Mit freundlichen Grüßen\n{mandate.creditor_name}\n"
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [mandate.debtor_email], fail_silently=False)
    item.status = SepaBatchItem.Status.PRENOTIFIED
    item.prenotified_at = timezone.now()
    item.save(update_fields=["status", "prenotified_at"])
    return True


def send_prenotifications_for_batch(batch: SepaBatch) -> int:
    sent = 0
    for item in batch.items.filter(status=SepaBatchItem.Status.PENDING).select_related("mandate"):
        if send_prenotification(item):
            sent += 1
    return sent


def find_expected_payment(payload: dict, provider: str) -> ExpectedPayment | None:
    metadata = payload.get("metadata") or payload.get("data", {}).get("metadata") or {}
    invoice_id = (
        metadata.get("invoice_id")
        or payload.get("invoice_id")
        or payload.get("reference")
        or payload.get("data", {}).get("invoice_id")
    )
    if invoice_id:
        payment = ExpectedPayment.objects.filter(invoice_id=invoice_id).first()
        if payment:
            return payment
    external_id = payload.get("id") or payload.get("data", {}).get("id")
    if external_id:
        link = PaymentLink.objects.filter(external_id=external_id).first()
        if link:
            return link.expected_payment
    return None


def extract_amount(payload: dict, provider: str) -> tuple[Decimal | None, str]:
    try:
        if provider == "stripe":
            data = payload.get("data", {}).get("object", {})
            total = data.get("amount_total")
            return (Decimal(total) / Decimal("100") if total is not None else None, data.get("currency", "").upper())
        if provider == "paypal":
            resource = payload.get("resource", {})
            amount = resource.get("amount", {})
            return (Decimal(str(amount.get("value"))) if amount.get("value") else None, amount.get("currency_code", ""))
        amount = payload.get("amount")
        return (Decimal(str(amount)) if amount is not None else None, payload.get("currency", ""))
    except Exception:  # noqa: BLE001
        return None, ""


def process_payment_event(provider: str, payload: dict, signature_valid: bool, config: PaymentProviderConfig | None = None) -> PaymentEvent:
    event_id = (
        payload.get("id")
        or payload.get("event_id")
        or hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    )
    event, created = PaymentEvent.objects.get_or_create(
        event_id=str(event_id),
        defaults={
            "provider": provider,
            "event_type": payload.get("type", ""),
            "payload": payload,
            "signature_valid": signature_valid,
            "currency": extract_amount(payload, provider)[1],
            "amount": extract_amount(payload, provider)[0],
            "external_ref": str(event_id),
        },
    )
    if event.processed:
        return event

    expected_payment = find_expected_payment(payload, provider)
    event.expected_payment = expected_payment
    if not expected_payment:
        event.processing_error = "Keine passende erwartete Zahlung gefunden."
        event.save(update_fields=["expected_payment", "processing_error"])
        return event

    try:
        erp_config = expected_payment.erp_config or active_config()
        reference = ""
        if erp_config and erp_config.has_credentials:
            transit_account = {
                "stripe": erp_config.transit_account_stripe,
                "paypal": erp_config.transit_account_paypal,
                "wero": erp_config.transit_account_wero,
            }.get(provider, erp_config.transit_account_stripe)
            client = ERPNextClient(erp_config)
            result = client.create_payment_entry(
                expected_payment=expected_payment,
                transaction=_TransitTransaction(event.external_ref, event.created_at.date()),
                matched_amount=event.amount or expected_payment.amount,
                deductions=[],
                references=[
                    {
                        "invoice_id": expected_payment.invoice_id,
                        "erp_name": expected_payment.erp_name,
                        "amount": str(event.amount or expected_payment.amount),
                    }
                ],
            )
            reference = result.get("name", "")
            event.processing_error = f"Geldtransit {transit_account}; Payment Entry {reference}"
        else:
            event.processing_error = f"Mock-Verbuchung auf Geldtransit {provider}."
            reference = f"MOCK-TRANSIT-{provider.upper()}-{expected_payment.invoice_id}"

        expected_payment.status = ExpectedPayment.Status.PAID
        expected_payment.paid_at = timezone.now()
        expected_payment.save(update_fields=["status", "paid_at"])
        PaymentLink.objects.filter(expected_payment=expected_payment, provider=provider).update(
            status=PaymentLink.Status.PAID, paid_at=timezone.now()
        )
        event.processed = True
        event.save(update_fields=["expected_payment", "processed", "processing_error"])
    except Exception as exc:  # noqa: BLE001
        logger.exception("Payment-Event-Verarbeitung fehlgeschlagen")
        event.processing_error = str(exc)
        event.save(update_fields=["processing_error"])
    return event


class _TransitTransaction:
    """Minimaler Transaction-Adapter für den ERP-Payment-Entry."""

    def __init__(self, external_id: str, booking_date):
        self.external_id = external_id
        self.booking_date = booking_date


def verify_stripe_signature(payload: bytes, header: str, secret: str, tolerance: int | None = None) -> bool:
    if not secret:
        return bool(settings.DEBUG)
    tolerance = tolerance or getattr(settings, "STRIPE_WEBHOOK_TOLERANCE_SECONDS", 300)
    try:
        parts = dict(part.split("=", 1) for part in header.split(","))
        timestamp = int(parts.get("t", "0"))
        signature = parts.get("v1", "")
        if abs(time.time() - timestamp) > tolerance:
            return False
        signed = f"{timestamp}.{payload.decode('utf-8')}".encode()
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:  # noqa: BLE001
        return False


def verify_hmac_signature(payload: bytes, header: str, secret: str) -> bool:
    if not secret:
        return bool(settings.DEBUG)
    try:
        provided = (header or "").strip()
        if provided.startswith("sha256="):
            provided = provided.split("=", 1)[1]
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, provided)
    except Exception:  # noqa: BLE001
        return False


def provider_secret(provider: str, config: PaymentProviderConfig | None) -> str:
    if config and config.webhook_secret:
        return config.webhook_secret
    return {
        "stripe": getattr(settings, "STRIPE_WEBHOOK_SECRET", ""),
        "paypal": getattr(settings, "PAYPAL_WEBHOOK_SECRET", ""),
        "wero": getattr(settings, "WERO_WEBHOOK_SECRET", ""),
    }.get(provider, "")
