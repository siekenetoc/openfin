from __future__ import annotations

import json
import logging
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger("openfin.erp")


class ERPNextError(RuntimeError):
    pass


class ERPNextClient:
    """Minimaler Frappe-REST-Client für Payment Entries und Purchase Invoices."""

    def __init__(self, config=None, timeout: int = 20):
        self.config = config
        self.timeout = timeout
        self.base_url = (getattr(config, "erp_base_url", "") or settings.ERPNEXT_BASE_URL).rstrip("/")
        self.api_key = getattr(config, "api_key", "") or settings.ERPNEXT_API_KEY
        self.api_secret = getattr(config, "api_secret", "") or settings.ERPNEXT_API_SECRET
        self.session = requests.Session()

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"token {self.api_key}:{self.api_secret}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        response = self.session.request(method, url, headers=self.headers, timeout=self.timeout, **kwargs)
        if response.status_code >= 400:
            raise ERPNextError(f"{method} {path} → HTTP {response.status_code}: {response.text[:500]}")
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return {"raw": response.text}

    def test_connection(self) -> dict:
        return self._request("GET", "/api/method/frappe.auth.get_logged_user")

    def create_payment_entry(
        self,
        expected_payment,
        transaction,
        matched_amount: Decimal,
        deductions: list | None = None,
        references: list | None = None,
    ) -> dict:
        config = expected_payment.erp_config or self.config
        references = references or [
            {
                "invoice_id": expected_payment.invoice_id,
                "erp_name": expected_payment.erp_name,
                "amount": str(matched_amount),
            }
        ]
        erp_references = [
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": ref.get("erp_name") or ref.get("invoice_id"),
                "allocated_amount": float(Decimal(str(ref.get("amount", "0")))),
            }
            for ref in references
        ]
        payload = {
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "company": getattr(config, "company", "") or None,
            "party_type": "Customer",
            "party": expected_payment.customer_name,
            "paid_amount": float(matched_amount),
            "received_amount": float(matched_amount),
            "reference_no": transaction.external_id,
            "reference_date": transaction.booking_date.isoformat(),
            "paid_from": getattr(config, "default_credit_account", "") or None,
            "paid_to": getattr(config, "default_debit_account", "") or None,
            "references": erp_references,
            "deductions": deductions or [],
            "remarks": f"OpenFin Auto-Reconciliation {transaction.external_id}",
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        return self._request("POST", "/api/resource/Payment Entry", json=payload)

    def get_purchase_invoices(self) -> list[dict]:
        filters = [["docstatus", "=", 1], ["status", "!=", "Paid"]]
        fields = [
            "name",
            "bill_no",
            "supplier",
            "supplier_name",
            "grand_total",
            "currency",
            "posting_date",
            "due_date",
            "remarks",
            "status",
        ]
        result = self._request(
            "GET",
            "/api/resource/Purchase Invoice",
            params={
                "filters": json.dumps(filters),
                "fields": json.dumps(fields),
                "limit_page_length": 200,
                "order_by": "due_date asc",
            },
        )
        return result.get("data", [])

    def get_sales_invoice(self, name: str) -> dict:
        return self._request("GET", f"/api/resource/Sales Invoice/{name}")
