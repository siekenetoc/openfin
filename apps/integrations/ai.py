from __future__ import annotations

import json
import logging
import re
from decimal import Decimal

from django.conf import settings
from django.db import connection

from apps.banking.models import BankTransaction

from .models import AICategorization, AIQuery

logger = logging.getLogger("openfin.ai")

ALLOWED_TABLES = {
    "banking_banktransaction",
    "banking_bankaccount",
    "erp_expectedpayment",
    "erp_reconciliationmatch",
    "billing_sepamandate",
    "billing_sepabatch",
    "billing_sepabatchitem",
    "providers_depotposition",
}
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|copy|vacuum|call|do)\b",
    re.IGNORECASE,
)


class LocalAIError(RuntimeError):
    pass


class LocalAIClient:
    def __init__(self):
        self.base_url = settings.LOCAL_LLM_BASE_URL
        self.api_key = settings.LOCAL_LLM_API_KEY
        self.model = settings.LOCAL_LLM_MODEL

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _client(self):
        from openai import OpenAI

        return OpenAI(base_url=self.base_url, api_key=self.api_key)

    def categorize(self, transaction: BankTransaction) -> AICategorization:
        if not self.configured:
            return self._heuristic(transaction)
        prompt = (
            "Kategorisiere den folgenden Bankumsatz. Antworte ausschließlich als JSON mit den Feldern "
            'category (kurz, deutsch), cost_center (optional) und confidence (0-1).\n'
            f"Gegenpartei: {transaction.counterparty_name}\n"
            f"Verwendungszweck: {transaction.purpose}\n"
            f"Betrag: {transaction.amount} {transaction.currency}\n"
        )
        try:
            response = self._client().chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du bist ein präziser Buchhaltungs-Kategorisierer."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
            categorization = AICategorization.objects.create(
                transaction=transaction,
                model=self.model,
                category=data.get("category", "Sonstiges")[:120],
                cost_center=(data.get("cost_center") or "")[:120],
                confidence=Decimal(str(data.get("confidence", 0))) * 100,
                raw_response=data,
            )
            return categorization
        except Exception as exc:  # noqa: BLE001
            logger.exception("Lokale KI-Kategorisierung fehlgeschlagen")
            categorization = self._heuristic(transaction)
            categorization.raw_response = {"error": str(exc)}
            categorization.save(update_fields=["raw_response"])
            return categorization

    def _heuristic(self, transaction: BankTransaction) -> AICategorization:
        text = f"{transaction.purpose} {transaction.counterparty_name}".lower()
        category = "Sonstiges"
        cost_center = ""
        confidence = Decimal("35.00")
        rules = [
            ("amazon", "Einkauf / Material", "Einkauf", "70"),
            ("miete", "Miete", "Raumkosten", "80"),
            ("telekom", "Telefon / Internet", "IT", "75"),
            ("rechnung", "Umsatzerlöse", "Vertrieb", "55"),
            ("gehalt", "Personal", "Personal", "80"),
            ("finanzamt", "Steuern", "Steuern", "85"),
        ]
        for needle, cat, cc, conf in rules:
            if needle in text:
                category, cost_center, confidence = cat, cc, Decimal(conf)
                break
        return AICategorization.objects.create(
            transaction=transaction,
            model="heuristic-fallback",
            category=category,
            cost_center=cost_center,
            confidence=confidence,
            raw_response={"fallback": True},
        )

    def text_to_sql(self, question: str, max_rows: int = 200) -> dict:
        query_log = AIQuery(question=question)
        if not self.configured:
            query_log.error = "Lokale KI ist nicht konfiguriert."
            query_log.save()
            raise LocalAIError(query_log.error)
        schema = (
            "banking_banktransaction(id, account_id, booking_date, amount, currency, counterparty_name, "
            "counterparty_iban, purpose, category, cost_center, status, confidence_score); "
            "banking_bankaccount(id, name, account_type, iban, balance, currency); "
            "erp_expectedpayment(id, invoice_id, customer_name, amount, currency, issue_date, due_date, status)"
        )
        prompt = (
            "Erzeuge eine einzelne PostgreSQL-SELECT-Abfrage für die folgende Frage. "
            "Erlaubte Tabellen: " + schema + ". Keine Kommentare, kein Semikolon, nur SELECT. "
            f"Frage: {question}"
        )
        try:
            response = self._client().chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du bist ein SQL-Generator. Antworte nur mit SQL."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
            sql = (response.choices[0].message.content or "").strip().strip("`")
        except Exception as exc:  # noqa: BLE001
            query_log.error = str(exc)
            query_log.save()
            raise LocalAIError(str(exc)) from exc

        safe_sql = self._validate_sql(sql, max_rows)
        query_log.generated_sql = safe_sql
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = 5000")
                cursor.execute(safe_sql)
                columns = [col.name for col in cursor.description]
                rows = cursor.fetchmany(max_rows)
            query_log.row_count = len(rows)
            query_log.save()
            return {"sql": safe_sql, "columns": columns, "rows": [list(row) for row in rows]}
        except Exception as exc:  # noqa: BLE001
            query_log.error = str(exc)
            query_log.save()
            raise LocalAIError(str(exc)) from exc

    @staticmethod
    def _validate_sql(sql: str, max_rows: int) -> str:
        cleaned = sql.strip().rstrip(";").strip()
        if not cleaned.lower().startswith("select"):
            raise LocalAIError("Nur SELECT-Abfragen sind erlaubt.")
        if ";" in cleaned:
            raise LocalAIError("Mehrfachanweisungen sind nicht erlaubt.")
        if FORBIDDEN_SQL.search(cleaned):
            raise LocalAIError("Nicht erlaubte SQL-Anweisung.")
        lowered = cleaned.lower()
        if " from " not in lowered:
            raise LocalAIError("Abfrage enthält keine FROM-Klausel.")
        table_part = lowered.split(" from ", 1)[1]
        table_part = re.split(r"\b(where|join|group|order|limit)\b", table_part)[0]
        tables = re.findall(r"[a-z_][a-z0-9_]*", table_part)
        if not any(table in ALLOWED_TABLES for table in tables):
            raise LocalAIError("Abfrage nutzt keine erlaubte Tabelle.")
        if not re.search(r"\blimit\b", lowered):
            cleaned = f"{cleaned} LIMIT {max_rows}"
        return cleaned


def categorize_uncategorized(limit: int = 50) -> int:
    client = LocalAIClient()
    count = 0
    for tx in BankTransaction.objects.filter(category="").order_by("-booking_date")[:limit]:
        categorization = client.categorize(tx)
        tx.category = categorization.category
        tx.cost_center = categorization.cost_center
        tx.save(update_fields=["category", "cost_center"])
        categorization.accepted = True
        categorization.save(update_fields=["accepted"])
        count += 1
    return count
