import hashlib
import hmac
import json
from datetime import date, timedelta

import pytest

from apps.billing.models import PaymentEvent, PaymentLink, PaymentProviderConfig
from apps.erp.models import ExpectedPayment


@pytest.mark.django_db
@pytest.mark.integration
def test_wero_webhook_marks_invoice_paid(tenant_ctx, client):
    PaymentProviderConfig.objects.create(provider="wero", webhook_secret="wero-secret", is_active=True)
    payment = ExpectedPayment.objects.create(
        invoice_id="RE-2026-0099",
        customer_name="Wero AG",
        amount=100,
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=10),
    )
    payload = {
        "id": "evt-wero-1",
        "type": "payment.completed",
        "invoice_id": payment.invoice_id,
        "amount": "100.00",
        "currency": "EUR",
    }
    body = json.dumps(payload).encode()
    signature = hmac.new(b"wero-secret", body, hashlib.sha256).hexdigest()
    response = client.post(
        "/api/webhooks/payments/wero/",
        data=body,
        content_type="application/json",
        HTTP_HOST="test.localhost",
        HTTP_X_WEBHOOK_SIGNATURE=signature,
    )
    assert response.status_code == 200, response.content
    payment.refresh_from_db()
    assert payment.status == ExpectedPayment.Status.PAID
    assert PaymentEvent.objects.filter(processed=True).exists()


@pytest.mark.django_db
@pytest.mark.integration
def test_webhook_rejects_invalid_signature(tenant_ctx, client):
    PaymentProviderConfig.objects.create(provider="stripe", webhook_secret="stripe-secret", is_active=True)
    response = client.post(
        "/api/webhooks/payments/stripe/",
        data=b"{}",
        content_type="application/json",
        HTTP_HOST="test.localhost",
        HTTP_STRIPE_SIGNATURE="t=1,v1=bad",
    )
    assert response.status_code == 403
