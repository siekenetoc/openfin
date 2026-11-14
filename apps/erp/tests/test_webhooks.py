import hashlib
import hmac
import json
from datetime import date, timedelta

import pytest

from apps.erp.models import ERPConfig, ExpectedPayment


@pytest.mark.django_db
@pytest.mark.integration
def test_sales_invoice_webhook_creates_expected_payment(tenant_ctx, client, rf):
    config = ERPConfig.objects.create(
        name="ERP",
        erp_base_url="http://erp.local",
        webhook_secret="top-secret",
    )
    payload = {
        "data": {
            "name": "SINV-0001",
            "invoice_id": "RE-2026-0042",
            "customer_name": "Musterkunde GmbH",
            "customer_iban": "DE02120300000000202051",
            "grand_total": "1250.00",
            "currency": "EUR",
            "posting_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=14)).isoformat(),
        }
    }
    body = json.dumps(payload).encode()
    signature = hmac.new(b"top-secret", body, hashlib.sha256).hexdigest()
    response = client.post(
        "/api/webhooks/erpnext/sales-invoice/",
        data=body,
        content_type="application/json",
        HTTP_HOST="test.localhost",
        HTTP_X_FRAPPE_WEBHOOK_SIGNATURE=signature,
    )
    assert response.status_code == 200, response.content
    payment = ExpectedPayment.objects.get(invoice_id="RE-2026-0042")
    assert payment.amount == 1250
    assert payment.customer_name == "Musterkunde GmbH"


@pytest.mark.django_db
@pytest.mark.integration
def test_sales_invoice_webhook_rejects_bad_signature(tenant_ctx, client):
    ERPConfig.objects.create(name="ERP", erp_base_url="http://erp.local", webhook_secret="top-secret")
    response = client.post(
        "/api/webhooks/erpnext/sales-invoice/",
        data=b"{}",
        content_type="application/json",
        HTTP_HOST="test.localhost",
        HTTP_X_FRAPPE_WEBHOOK_SIGNATURE="deadbeef",
    )
    assert response.status_code == 403
