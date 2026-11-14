from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import requests
from django.conf import settings

from apps.banking.models import BankTransaction

from .models import PaperlessDocumentLink

logger = logging.getLogger("openfin.paperless")


class PaperlessError(RuntimeError):
    pass


class PaperlessClient:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or settings.PAPERLESS_API_URL).rstrip("/")
        self.token = token or settings.PAPERLESS_API_TOKEN
        self.session = requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Token {self.token}", "Accept": "application/json"}

    def search(self, query: str, limit: int = 10) -> list[dict]:
        if not self.configured:
            raise PaperlessError("Paperless-ngx ist nicht konfiguriert.")
        response = self.session.get(
            f"{self.base_url}/documents/",
            headers=self.headers,
            params={"query": query, "page_size": limit, "ordering": "-created"},
            timeout=20,
        )
        if response.status_code >= 400:
            raise PaperlessError(f"Paperless-Suche fehlgeschlagen: {response.status_code}")
        return response.json().get("results", [])

    def document(self, document_id: str) -> dict:
        response = self.session.get(f"{self.base_url}/documents/{document_id}/", headers=self.headers, timeout=20)
        response.raise_for_status()
        return response.json()

    def find_for_transaction(self, tx: BankTransaction) -> tuple[dict | None, int]:
        amount = f"{abs(tx.amount):.2f}"
        query_parts = [amount, tx.booking_date.strftime("%d.%m.%Y")]
        if tx.counterparty_name:
            query_parts.append(tx.counterparty_name)
        query = " ".join(query_parts)
        try:
            results = self.search(query, limit=15)
        except PaperlessError:
            raise
        best = None
        best_score = 0
        for document in results:
            text = " ".join(
                str(value)
                for key, value in document.items()
                if key in {"title", "content", "original_file_name", "correspondent", "document_type"}
            ).lower()
            score = 0
            if amount in text:
                score += 40
            if tx.booking_date.strftime("%Y-%m-%d") in text or tx.booking_date.strftime("%d.%m.%Y") in text:
                score += 30
            if tx.counterparty_name and tx.counterparty_name.lower() in text:
                score += 20
            if tx.purpose and any(part.lower() in text for part in tx.purpose.split()[:3]):
                score += 10
            if score > best_score:
                best, best_score = document, score
        return best, min(best_score, 100)

    def link_transaction(self, tx: BankTransaction, document: dict, score: int = 0) -> PaperlessDocumentLink:
        document_id = str(document.get("id"))
        url = f"{self.base_url}/documents/{document_id}/"
        link, _ = PaperlessDocumentLink.objects.update_or_create(
            transaction=tx,
            document_id=document_id,
            defaults={
                "title": document.get("title", ""),
                "url": url,
                "match_score": score,
            },
        )
        tx.paperless_document_id = document_id
        tx.linked_document_url = url
        tx.save(update_fields=["paperless_document_id", "linked_document_url"])
        return link

    def autolink(self, limit: int = 100) -> int:
        linked = 0
        candidates = BankTransaction.objects.filter(paperless_document_id="", amount__lt=0)[:limit]
        for tx in candidates:
            try:
                document, score = self.find_for_transaction(tx)
                if document and score >= 50:
                    self.link_transaction(tx, document, score)
                    linked += 1
            except PaperlessError:
                logger.warning("Paperless-Abgleich nicht möglich")
                break
            except Exception:  # noqa: BLE001
                logger.exception("Paperless-Abgleich für Transaktion %s fehlgeschlagen", tx.pk)
        return linked
