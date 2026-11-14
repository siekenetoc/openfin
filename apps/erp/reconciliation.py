"""3-Stufen-Reconciliation-Engine mit Confidence Score (0–100)."""

from __future__ import annotations

import itertools
import logging
import re
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.utils import timezone

from apps.banking.models import BankTransaction, CategoryRule
from apps.erp.models import ExpectedPayment, ReconciliationMatch

logger = logging.getLogger("openfin.reconciliation")

AUTO_THRESHOLD = 95
REVIEW_THRESHOLD = 50


@dataclass
class Candidate:
    payment: ExpectedPayment
    score: int
    stage: str
    matched_amount: Decimal
    discount_amount: Decimal = Decimal("0.00")
    references: list = field(default_factory=list)
    deductions: list = field(default_factory=list)


INVOICE_PATTERNS = [
    re.compile(r"\bRE[-\s/]?(\d{4})[-\s/]?(\d{3,6})\b", re.IGNORECASE),
    re.compile(r"\b(?:RG|RECHNUNG|INVOICE|INV)\.?\s*(?:NR\.?)?\s*(\d{2})[/-](\d{2,6})\b", re.IGNORECASE),
    re.compile(r"\b(\d{2})/(\d{2,6})\b"),
]


def normalize_purpose(text: str) -> str:
    """Bereinigt Verwendungszwecke und normalisiert Rechnungsnummern."""
    if not text:
        return ""
    normalized = text.upper().replace("ß", "SS")
    normalized = re.sub(r"[.,;:_]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    def replace_rg(match: re.Match) -> str:
        year, number = match.group(1), match.group(2).zfill(4)
        return f"RE-20{year}-{number}"

    normalized = re.sub(
        r"\b(?:RG|RECHNUNG|INVOICE|INV)\.?\s*(?:NR\.?)?\s*(\d{2})[/-](\d{2,6})\b",
        replace_rg,
        normalized,
    )
    return normalized


def extract_invoice_ids(text: str) -> list[str]:
    ids: list[str] = []
    normalized = normalize_purpose(text)
    for pattern in INVOICE_PATTERNS:
        for match in pattern.finditer(normalized):
            if len(match.groups()) != 2:
                continue
            first, second = match.group(1), match.group(2)
            if len(first) == 4:
                ids.append(f"RE-{first}-{second.zfill(4)}")
            elif len(first) == 2:
                ids.append(f"RE-20{first}-{second.zfill(4)}")
    seen = set()
    result = []
    for invoice in ids:
        if invoice not in seen:
            seen.add(invoice)
            result.append(invoice)
    return result


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    try:
        from rapidfuzz import fuzz

        return fuzz.token_set_ratio(a, b) / 100.0
    except Exception:  # noqa: BLE001
        from difflib import SequenceMatcher

        return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _iban_match(tx: BankTransaction, payment: ExpectedPayment) -> bool:
    if not tx.counterparty_iban or not payment.customer_iban:
        return False
    return tx.counterparty_iban.replace(" ", "").upper()[-10:] == payment.customer_iban.replace(" ", "").upper()[-10:]


def _amount_score(tx: BankTransaction, payment: ExpectedPayment) -> tuple[int, Decimal, Decimal, str]:
    amount = abs(tx.amount)
    if abs(amount - payment.amount) <= Decimal("0.01"):
        return 30, payment.amount, Decimal("0.00"), "exakt"
    if tx.booking_date <= payment.issue_date + timedelta(days=payment.discount_days):
        expected = payment.discounted_amount
        if abs(amount - expected) <= Decimal("0.03"):
            discount = payment.amount - amount
            return 26, amount, discount.quantize(Decimal("0.01")), f"skonto_{payment.discount_rate}"
    # Rundungstoleranz (z. B. ausländische Gebühren / Bankrundung)
    if abs(amount - payment.amount) <= Decimal("0.05"):
        return 22, amount, Decimal("0.00"), "rundung"
    return 0, amount, Decimal("0.00"), ""


def score_payment(tx: BankTransaction, payment: ExpectedPayment) -> Candidate | None:
    amount_points, matched_amount, discount, amount_kind = _amount_score(tx, payment)
    if amount_points == 0:
        return None

    normalized_purpose = normalize_purpose(tx.purpose)
    invoice_ids = extract_invoice_ids(tx.purpose)
    payment_invoice = normalize_purpose(payment.invoice_id)

    invoice_points = 0
    if payment_invoice in invoice_ids or payment_invoice == normalized_purpose:
        invoice_points = 40
    else:
        best_invoice_ratio = max(
            [_ratio(payment_invoice, candidate) for candidate in invoice_ids] or [0.0]
        )
        purpose_ratio = _ratio(payment_invoice, normalized_purpose)
        invoice_points = int(max(best_invoice_ratio, purpose_ratio) * 38)

    name_points = int(_ratio(normalize_purpose(tx.counterparty_name), normalize_purpose(payment.customer_name)) * 15)
    purpose_points = int(_ratio(normalized_purpose, normalize_purpose(payment.description)) * 8)
    iban_points = 10 if _iban_match(tx, payment) else 0
    date_points = 5 if payment.issue_date <= tx.booking_date <= payment.due_date + timedelta(days=10) else 0

    score = min(100, amount_points + invoice_points + name_points + purpose_points + iban_points + date_points)
    if score < REVIEW_THRESHOLD:
        return None

    stage = ReconciliationMatch.Stage.SKONTO if amount_kind.startswith("skonto") else ReconciliationMatch.Stage.TRIGRAM
    deductions = []
    if discount > 0 and payment.erp_config_id:
        deductions.append(
            {
                "account": payment.erp_config.skonto_account,
                "amount": str(discount),
                "cost_center": "Skonto",
            }
        )
    return Candidate(
        payment=payment,
        score=score,
        stage=stage,
        matched_amount=matched_amount,
        discount_amount=discount,
        references=[
            {
                "invoice_id": payment.invoice_id,
                "erp_name": payment.erp_name,
                "amount": str(matched_amount),
                "discount": str(discount),
            }
        ],
        deductions=deductions,
    )


def _candidate_payments(tx: BankTransaction) -> list[ExpectedPayment]:
    qs = ExpectedPayment.objects.filter(status=ExpectedPayment.Status.OPEN).select_related("erp_config")
    if connection.vendor == "postgresql":
        try:
            from django.contrib.postgres.search import TrigramSimilarity

            normalized = normalize_purpose(tx.purpose)
            return list(
                qs.annotate(
                    invoice_sim=TrigramSimilarity("invoice_id", normalized),
                    customer_sim=TrigramSimilarity("customer_name", tx.counterparty_name or ""),
                )
                .filter(invoice_sim__gt=0.05)
                .order_by("-invoice_sim", "-customer_sim", "due_date")[:60]
            )
        except Exception:  # noqa: BLE001
            logger.debug("Trigram-Prefilter nicht verfügbar; nutze Python-Fallback.")
    return list(qs.order_by("due_date")[:200])


def find_subset(tx: BankTransaction, payments: list[ExpectedPayment]) -> Candidate | None:
    """Stufe 3: findet eine Teilmenge offener Rechnungen, deren Summe zur Zahlung passt."""
    target = abs(tx.amount)
    if target <= 0 or len(payments) < 2:
        return None

    relevant = payments
    if tx.counterparty_iban:
        iban_matched = [
            payment for payment in payments if _iban_match(tx, payment)
        ]
        if iban_matched:
            relevant = iban_matched
    elif tx.counterparty_name:
        name_matched = [
            payment
            for payment in payments
            if _ratio(normalize_purpose(tx.counterparty_name), normalize_purpose(payment.customer_name)) > 0.65
        ]
        if name_matched:
            relevant = name_matched

    relevant = sorted(relevant, key=lambda payment: payment.amount, reverse=True)[:12]
    if len(relevant) < 2:
        return None

    for size in range(2, min(6, len(relevant)) + 1):
        for combo in itertools.combinations(relevant, size):
            total = sum((payment.amount for payment in combo), Decimal("0.00"))
            if abs(total - target) <= Decimal("0.02"):
                return _subset_candidate(combo, target, Decimal("0.00"), 98)
            for rate in {payment.discount_rate for payment in combo}:
                discounted = (total * (100 - rate) / Decimal("100")).quantize(Decimal("0.01"))
                if abs(discounted - target) <= Decimal("0.03"):
                    return _subset_candidate(combo, target, (total - target).quantize(Decimal("0.01")), 96)
    return None


def _subset_candidate(combo, target: Decimal, discount: Decimal, score: int) -> Candidate:
    references = [
        {
            "invoice_id": payment.invoice_id,
            "erp_name": payment.erp_name,
            "amount": str(payment.amount),
        }
        for payment in combo
    ]
    deductions = []
    if discount > 0:
        first_config = next((payment.erp_config for payment in combo if payment.erp_config_id), None)
        deductions.append(
            {
                "account": first_config.skonto_account if first_config else "Skontoaufwand",
                "amount": str(discount),
            }
        )
    return Candidate(
        payment=combo[0],
        score=score,
        stage=ReconciliationMatch.Stage.SUBSET,
        matched_amount=target,
        discount_amount=discount,
        references=references,
        deductions=deductions,
    )


def apply_category_rules(tx: BankTransaction) -> None:
    haystack = f"{tx.purpose} {tx.counterparty_name}"
    for rule in CategoryRule.objects.filter(is_active=True).order_by("priority"):
        if rule.matches(haystack):
            tx.category = rule.category
            tx.cost_center = rule.cost_center
            tx.save(update_fields=["category", "cost_center"])
            return


def reconcile_transaction(tx: BankTransaction) -> dict:
    if tx.status in {
        BankTransaction.Status.MATCHED,
        BankTransaction.Status.AUTO_RECONCILED,
        BankTransaction.Status.IGNORED,
    }:
        return {"status": tx.status, "score": tx.confidence_score}
    if tx.amount <= 0:
        apply_category_rules(tx)
        return {"status": tx.status, "score": 0, "detail": "kein Zahlungseingang"}

    payments = _candidate_payments(tx)
    candidates = [candidate for payment in payments if (candidate := score_payment(tx, payment))]
    candidates.sort(key=lambda candidate: (candidate.score, candidate.payment.due_date), reverse=True)

    # Stufe 3 benötigt alle offenen Posten (auch ohne Purpose-Ähnlichkeit).
    all_open = list(
        ExpectedPayment.objects.filter(status=ExpectedPayment.Status.OPEN)
        .select_related("erp_config")
        .order_by("due_date")[:200]
    )
    best = candidates[0] if candidates else None
    subset = find_subset(tx, all_open)

    if subset and (best is None or subset.score >= best.score):
        return _persist_candidate(tx, subset)
    if best is None:
        apply_category_rules(tx)
        tx.status = BankTransaction.Status.UNMATCHED
        tx.confidence_score = 0
        tx.save(update_fields=["status", "confidence_score"])
        return {"status": tx.status, "score": 0}

    return _persist_candidate(tx, best)


def _persist_candidate(tx: BankTransaction, candidate: Candidate) -> dict:
    tx.confidence_score = candidate.score
    if candidate.score > AUTO_THRESHOLD:
        match = ReconciliationMatch.objects.create(
            transaction=tx,
            expected_payment=candidate.payment,
            score=candidate.score,
            stage=candidate.stage,
            status=ReconciliationMatch.Status.AUTO,
            matched_amount=candidate.matched_amount,
            discount_amount=candidate.discount_amount,
            deductions=candidate.deductions,
            references=candidate.references,
        )
        _book_match(match)
        tx.status = BankTransaction.Status.AUTO_RECONCILED
    else:
        ReconciliationMatch.objects.update_or_create(
            transaction=tx,
            expected_payment=candidate.payment,
            defaults={
                "score": candidate.score,
                "stage": candidate.stage,
                "status": ReconciliationMatch.Status.PROPOSED,
                "matched_amount": candidate.matched_amount,
                "discount_amount": candidate.discount_amount,
                "deductions": candidate.deductions,
                "references": candidate.references,
            },
        )
        tx.status = BankTransaction.Status.NEEDS_REVIEW
    tx.save(update_fields=["status", "confidence_score"])
    return {
        "status": tx.status,
        "score": candidate.score,
        "payment_id": candidate.payment.pk,
        "invoice_id": candidate.payment.invoice_id,
        "stage": candidate.stage,
    }


def approve_match(match: ReconciliationMatch) -> ReconciliationMatch:
    if match.status in {ReconciliationMatch.Status.CONFIRMED, ReconciliationMatch.Status.AUTO}:
        return match
    _book_match(match)
    match.status = ReconciliationMatch.Status.CONFIRMED
    match.save(update_fields=["status", "erp_payment_entry"])
    match.transaction.status = BankTransaction.Status.MATCHED
    match.transaction.save(update_fields=["status"])
    return match


def reject_match(match: ReconciliationMatch) -> ReconciliationMatch:
    match.status = ReconciliationMatch.Status.REJECTED
    match.save(update_fields=["status"])
    tx = match.transaction
    remaining = tx.reconciliation_matches.filter(status=ReconciliationMatch.Status.PROPOSED).exclude(pk=match.pk)
    tx.status = BankTransaction.Status.NEEDS_REVIEW if remaining.exists() else BankTransaction.Status.UNMATCHED
    tx.save(update_fields=["status"])
    return match


def _book_match(match: ReconciliationMatch) -> None:
    from apps.erp.client import ERPNextClient

    payment = match.expected_payment
    config = payment.erp_config
    reference = ""
    if config and config.has_credentials:
        try:
            client = ERPNextClient(config)
            result = client.create_payment_entry(
                expected_payment=payment,
                transaction=match.transaction,
                matched_amount=match.matched_amount,
                deductions=match.deductions,
                references=match.references,
            )
            reference = result.get("name", "")
        except Exception as exc:  # noqa: BLE001
            logger.exception("ERPNext Payment Entry fehlgeschlagen")
            match.notes = f"ERP-Fehler: {exc}"
    else:
        reference = f"MOCK-PE-{payment.invoice_id}"

    match.erp_payment_entry = reference
    match.transaction.erp_payment_reference = reference
    match.transaction.save(update_fields=["erp_payment_reference"])

    payments_to_update = [payment]
    if match.references:
        invoice_ids = [ref.get("invoice_id") for ref in match.references if ref.get("invoice_id")]
        if len(invoice_ids) > 1:
            payments_to_update = list(ExpectedPayment.objects.filter(invoice_id__in=invoice_ids))
    now = timezone.now()
    for item in payments_to_update:
        matched_ref = next(
            (ref for ref in (match.references or []) if ref.get("invoice_id") == item.invoice_id),
            None,
        )
        matched_amount = (
            Decimal(str(matched_ref.get("amount", item.amount))) if matched_ref else match.matched_amount
        )
        if matched_amount >= item.amount - item.discount_amount - Decimal("0.02"):
            item.status = ExpectedPayment.Status.PAID
            item.paid_at = now
        else:
            item.status = ExpectedPayment.Status.PARTIAL
        item.save(update_fields=["status", "paid_at"])


def score_transaction_against_payment(tx: BankTransaction, payment: ExpectedPayment) -> int:
    candidate = score_payment(tx, payment)
    return candidate.score if candidate else 0
