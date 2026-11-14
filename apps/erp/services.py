from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.utils.dateparse import parse_date

from apps.banking.models import BankAccount, OutgoingPayment
from apps.billing.sepa import build_pain001

from .client import ERPNextClient, ERPNextError
from .models import ERPConfig, ExpectedPayment, PurchaseInvoice

logger = logging.getLogger("openfin.erp.services")


def active_config() -> ERPConfig | None:
    return ERPConfig.objects.filter(is_active=True).first()


def verify_webhook_signature(body: bytes, signature: str, secret: str | None = None) -> bool:
    secret = secret if secret is not None else settings.ERPNEXT_WEBHOOK_SECRET
    if not secret:
        return bool(settings.DEBUG)
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    provided = (signature or "").strip()
    if provided.startswith("sha256="):
        provided = provided.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


def process_sales_invoice(payload: dict, config: ERPConfig | None = None) -> ExpectedPayment:
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    invoice_id = (
        data.get("invoice_id")
        or data.get("name")
        or data.get("bill_no")
        or f"ERP-{data.get('posting_date', date.today())}"
    )
    issue_date = parse_date(str(data.get("posting_date") or date.today())) or date.today()
    due_date = parse_date(str(data.get("due_date") or issue_date)) or issue_date
    amount = Decimal(str(data.get("grand_total") or data.get("paid_amount") or "0.00"))
    discount_rate = Decimal(str(data.get("openfin_discount_rate") or getattr(config, "default_discount_rate", "2.00")))
    discount_days = int(data.get("openfin_discount_days") or getattr(config, "default_discount_days", 10))

    payment, _ = ExpectedPayment.objects.update_or_create(
        invoice_id=invoice_id,
        defaults={
            "erp_config": config or active_config(),
            "erp_name": data.get("name", ""),
            "customer_name": data.get("customer_name") or data.get("customer") or data.get("party_name") or "Unbekannt",
            "customer_iban": (data.get("customer_iban") or data.get("custom_customer_iban") or "").replace(" ", ""),
            "amount": amount,
            "currency": data.get("currency") or "EUR",
            "issue_date": issue_date,
            "due_date": due_date,
            "description": data.get("remarks") or data.get("description") or "",
            "discount_rate": discount_rate,
            "discount_days": discount_days,
            "raw_data": data,
            "status": ExpectedPayment.Status.OPEN,
        },
    )
    return payment


def sync_purchase_invoices(config: ERPConfig | None = None) -> dict:
    config = config or active_config()
    if not config or not config.has_credentials:
        return {"status": "skipped", "reason": "Keine ERPNext-Zugangsdaten konfiguriert."}
    client = ERPNextClient(config)
    invoices = client.get_purchase_invoices()
    created = 0
    queued = 0
    for data in invoices:
        invoice, was_created = PurchaseInvoice.objects.get_or_create(
            erp_name=data.get("name"),
            defaults={
                "erp_config": config,
                "invoice_id": data.get("bill_no") or data.get("name", ""),
                "supplier": data.get("supplier_name") or data.get("supplier", ""),
                "supplier_iban": data.get("supplier_iban") or "",
                "amount": Decimal(str(data.get("grand_total") or "0.00")),
                "currency": data.get("currency") or "EUR",
                "issue_date": parse_date(str(data.get("posting_date") or "")) or None,
                "due_date": parse_date(str(data.get("due_date") or "")) or None,
                "raw_data": data,
            },
        )
        if was_created:
            created += 1
        if config.default_bank_account and not invoice.outgoing_payment_id:
            payment = OutgoingPayment.objects.create(
                account=config.default_bank_account,
                payment_type=OutgoingPayment.PaymentType.SINGLE,
                recipient_name=invoice.supplier,
                recipient_iban=invoice.supplier_iban,
                amount=invoice.amount,
                currency=invoice.currency,
                purpose=f"Rechnung {invoice.invoice_id}",
                reference=invoice.invoice_id,
                status=OutgoingPayment.Status.DRAFT,
            )
            payment.pain_xml = build_pain001(payment)
            payment.save(update_fields=["pain_xml"])
            invoice.outgoing_payment = payment
            invoice.status = PurchaseInvoice.Status.QUEUED
            invoice.save(update_fields=["outgoing_payment", "status"])
            queued += 1
    return {"status": "ok", "fetched": len(invoices), "created": created, "queued": queued}
