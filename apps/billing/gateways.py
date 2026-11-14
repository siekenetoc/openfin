"""Payment-Gateway-Adapter für Stripe, PayPal und Wero (A2A)."""

from __future__ import annotations

import base64
import io
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlencode

import requests
from django.conf import settings

from .models import PaymentProviderConfig

logger = logging.getLogger("openfin.gateways")


@dataclass
class GatewayLink:
    url: str
    external_id: str
    qr_code: str = ""
    metadata: dict | None = None


def _config(provider: str) -> PaymentProviderConfig | None:
    return PaymentProviderConfig.objects.filter(provider=provider, is_active=True).first()


def _qr_data_uri(payload: str) -> str:
    try:
        import qrcode

        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception:  # noqa: BLE001
        return ""


def create_stripe_link(expected_payment, base_url: str = "") -> GatewayLink:
    config = _config(PaymentProviderConfig.Provider.STRIPE)
    external_id = f"cs_mock_{uuid.uuid4().hex[:20]}"
    if config and config.api_key:
        try:
            import stripe

            stripe.api_key = config.api_key
            session = stripe.checkout.Session.create(
                mode="payment",
                line_items=[
                    {
                        "price_data": {
                            "currency": expected_payment.currency.lower(),
                            "product_data": {"name": f"Rechnung {expected_payment.invoice_id}"},
                            "unit_amount": int(expected_payment.amount * 100),
                        },
                        "quantity": 1,
                    }
                ],
                success_url=f"{base_url or 'https://openfin.local'}/billing/success/",
                cancel_url=f"{base_url or 'https://openfin.local'}/billing/cancelled/",
                metadata={"invoice_id": expected_payment.invoice_id},
            )
            return GatewayLink(url=session.url, external_id=session.id, metadata={"mode": config.mode})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Stripe-Checkout fehlgeschlagen")
            raise RuntimeError(f"Stripe: {exc}") from exc
    url = f"https://checkout.stripe.com/c/pay/{external_id}"
    return GatewayLink(url=url, external_id=external_id, metadata={"mock": True})


def _paypal_token(config: PaymentProviderConfig) -> str:
    base = "https://api-m.sandbox.paypal.com" if config.mode != "live" else "https://api-m.paypal.com"
    response = requests.post(
        f"{base}/v1/oauth2/token",
        auth=(config.api_key, config.api_secret),
        data={"grant_type": "client_credentials"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def create_paypal_link(expected_payment, base_url: str = "") -> GatewayLink:
    config = _config(PaymentProviderConfig.Provider.PAYPAL)
    external_id = f"PAYPAL-MOCK-{uuid.uuid4().hex[:16]}"
    if config and config.api_key and config.api_secret:
        try:
            token = _paypal_token(config)
            base = "https://api-m.sandbox.paypal.com" if config.mode != "live" else "https://api-m.paypal.com"
            response = requests.post(
                f"{base}/v2/checkout/orders",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={
                    "intent": "CAPTURE",
                    "purchase_units": [
                        {
                            "reference_id": expected_payment.invoice_id,
                            "amount": {
                                "currency_code": expected_payment.currency,
                                "value": f"{expected_payment.amount:.2f}",
                            },
                        }
                    ],
                    "application_context": {
                        "return_url": f"{base_url or 'https://openfin.local'}/billing/success/",
                        "cancel_url": f"{base_url or 'https://openfin.local'}/billing/cancelled/",
                    },
                },
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            approve = next((link["href"] for link in data.get("links", []) if link["rel"] == "approve"), "")
            return GatewayLink(url=approve, external_id=data.get("id", external_id), metadata={"mock": False})
        except Exception as exc:  # noqa: BLE001
            logger.exception("PayPal-Order fehlgeschlagen")
            raise RuntimeError(f"PayPal: {exc}") from exc
    url = f"https://www.sandbox.paypal.com/checkoutnow?token={external_id}"
    return GatewayLink(url=url, external_id=external_id, metadata={"mock": True})


def create_wero_link(expected_payment, base_url: str = "") -> GatewayLink:
    config = _config(PaymentProviderConfig.Provider.WERO)
    reference = f"WERO-{uuid.uuid4().hex[:18].upper()}"
    query = urlencode(
        {
            "ref": reference,
            "amount": f"{expected_payment.amount:.2f}",
            "currency": expected_payment.currency,
            "invoice": expected_payment.invoice_id,
            "merchant": getattr(config, "merchant_id", "") or "OPENFIN",
        }
    )
    url = f"https://wero-wallet.eu/pay?{query}"
    link = GatewayLink(
        url=url,
        external_id=reference,
        qr_code=_qr_data_uri(url),
        metadata={"mock": not bool(config and config.api_key), "a2a": True},
    )
    if config and config.api_key:
        try:
            response = requests.post(
                f"{settings.WERO_API_BASE_URL.rstrip('/')}/payment-links",
                headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
                json={
                    "amount": f"{expected_payment.amount:.2f}",
                    "currency": expected_payment.currency,
                    "reference": reference,
                    "invoice_id": expected_payment.invoice_id,
                },
                timeout=20,
            )
            if response.ok:
                data = response.json()
                link.url = data.get("url", link.url)
                link.qr_code = data.get("qr_code", link.qr_code) or link.qr_code
                link.metadata = {"mock": False, "a2a": True}
        except Exception:  # noqa: BLE001
            logger.exception("Wero-API nicht erreichbar; lokaler A2A-Link wird verwendet.")
    return link


def create_gateway_link(expected_payment, provider: str, base_url: str = "") -> GatewayLink:
    if provider == "stripe":
        return create_stripe_link(expected_payment, base_url)
    if provider == "paypal":
        return create_paypal_link(expected_payment, base_url)
    if provider == "wero":
        return create_wero_link(expected_payment, base_url)
    raise ValueError(f"Unbekannter Provider: {provider}")
