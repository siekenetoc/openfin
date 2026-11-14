from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal

from apps.banking.models import BankAccount, BankTransaction, OutgoingPayment
from apps.billing.models import PaymentLink, SEPAMandate, SepaBatch, SepaBatchItem
from apps.erp.models import ExpectedPayment
from apps.integrations.models import PaperlessDocumentLink
from apps.providers.models import DepotPosition


def _de(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value:.2f}".replace(".", ",")
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _buffer_row(writer: csv.writer, buffer: io.StringIO, row: list) -> str:
    buffer.seek(0)
    buffer.truncate(0)
    writer.writerow(row)
    return buffer.getvalue()


def dataset_rows(dataset: str, filters: dict):
    """Generator für StreamingHttpResponse mit BOM und Semikolon (Excel/DATEV-freundlich)."""
    ids = [int(pk) for pk in filters.get("ids", "").split(",") if pk.strip().isdigit()]
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    status = filters.get("status", "")
    search = filters.get("q") or filters.get("search") or ""

    if dataset == "transactions":
        qs = BankTransaction.objects.select_related("account").all()
        if ids:
            qs = qs.filter(pk__in=ids)
        if date_from:
            qs = qs.filter(booking_date__gte=date_from)
        if date_to:
            qs = qs.filter(booking_date__lte=date_to)
        if status:
            qs = qs.filter(status=status)
        if search:
            from django.db.models import Q

            qs = qs.filter(Q(purpose__icontains=search) | Q(counterparty_name__icontains=search))
        headers = ["Datum", "Konto", "Betrag", "Währung", "Gegenpartei", "IBAN", "Verwendungszweck", "Kategorie", "Kostenstelle", "Status", "Score"]
        yield "\ufeff" + ";".join(headers) + "\r\n"
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
        for tx in qs.iterator():
            yield _buffer_row(
                writer,
                buffer,
                [
                    _de(tx.booking_date),
                    tx.account.name,
                    _de(tx.amount),
                    tx.currency,
                    tx.counterparty_name,
                    tx.counterparty_iban,
                    tx.purpose,
                    tx.category,
                    tx.cost_center,
                    tx.get_status_display(),
                    tx.confidence_score,
                ],
            )

    elif dataset == "expected":
        qs = ExpectedPayment.objects.all()
        if ids:
            qs = qs.filter(pk__in=ids)
        if date_from:
            qs = qs.filter(due_date__gte=date_from)
        if date_to:
            qs = qs.filter(due_date__lte=date_to)
        if status:
            qs = qs.filter(status=status)
        if search:
            from django.db.models import Q

            qs = qs.filter(Q(invoice_id__icontains=search) | Q(customer_name__icontains=search))
        headers = ["Rechnung", "Kunde", "Betrag", "Währung", "Rechnungsdatum", "Fälligkeit", "Status", "Skonto %", "Skontotage"]
        yield "\ufeff" + ";".join(headers) + "\r\n"
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
        for payment in qs.iterator():
            yield _buffer_row(
                writer,
                buffer,
                [
                    payment.invoice_id,
                    payment.customer_name,
                    _de(payment.amount),
                    payment.currency,
                    _de(payment.issue_date),
                    _de(payment.due_date),
                    payment.get_status_display(),
                    _de(payment.discount_rate),
                    payment.discount_days,
                ],
            )

    elif dataset == "sepa_items":
        qs = SepaBatchItem.objects.select_related("batch", "mandate").all()
        if ids:
            qs = qs.filter(pk__in=ids)
        if date_from:
            qs = qs.filter(batch__collection_date__gte=date_from)
        if date_to:
            qs = qs.filter(batch__collection_date__lte=date_to)
        if status:
            qs = qs.filter(status=status)
        headers = ["Batch", "Mandat", "Debitor", "IBAN", "Betrag", "Verwendungszweck", "Status", "Einzugsdatum"]
        yield "\ufeff" + ";".join(headers) + "\r\n"
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
        for item in qs.iterator():
            yield _buffer_row(
                writer,
                buffer,
                [
                    item.batch.batch_id,
                    item.mandate.mandate_reference,
                    item.mandate.debtor_name,
                    item.mandate.debtor_iban,
                    _de(item.amount),
                    item.purpose,
                    item.get_status_display(),
                    _de(item.batch.collection_date),
                ],
            )

    elif dataset == "depot":
        qs = DepotPosition.objects.select_related("account").all()
        if ids:
            qs = qs.filter(pk__in=ids)
        headers = ["Konto", "Name", "ISIN", "Stück", "Kurs", "Wert", "Währung", "Aktualisiert"]
        yield "\ufeff" + ";".join(headers) + "\r\n"
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
        for position in qs.iterator():
            yield _buffer_row(
                writer,
                buffer,
                [
                    position.account.name,
                    position.name,
                    position.isin,
                    _de(position.quantity),
                    _de(position.price),
                    _de(position.market_value),
                    position.currency,
                    _de(position.updated_at),
                ],
            )

    elif dataset == "payments":
        qs = OutgoingPayment.objects.select_related("account").all()
        if ids:
            qs = qs.filter(pk__in=ids)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        if status:
            qs = qs.filter(status=status)
        headers = ["Konto", "Typ", "Empfänger", "IBAN", "Betrag", "Währung", "Zweck", "Status", "Erstellt"]
        yield "\ufeff" + ";".join(headers) + "\r\n"
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
        for payment in qs.iterator():
            yield _buffer_row(
                writer,
                buffer,
                [
                    payment.account.name,
                    payment.get_payment_type_display(),
                    payment.recipient_name,
                    payment.recipient_iban,
                    _de(payment.amount),
                    payment.currency,
                    payment.purpose,
                    payment.get_status_display(),
                    _de(payment.created_at),
                ],
            )

    elif dataset == "sepa_batches":
        qs = SepaBatch.objects.select_related("account").all()
        if ids:
            qs = qs.filter(pk__in=ids)
        if date_from:
            qs = qs.filter(collection_date__gte=date_from)
        if date_to:
            qs = qs.filter(collection_date__lte=date_to)
        if status:
            qs = qs.filter(status=status)
        headers = ["Batch", "Konto", "Einzugsdatum", "Betrag", "Status", "Erstellt"]
        yield "\ufeff" + ";".join(headers) + "\r\n"
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
        for batch in qs.iterator():
            yield _buffer_row(
                writer,
                buffer,
                [
                    batch.batch_id,
                    batch.account.name,
                    _de(batch.collection_date),
                    _de(batch.total_amount),
                    batch.get_status_display(),
                    _de(batch.created_at),
                ],
            )

    elif dataset == "mandates":
        qs = SEPAMandate.objects.all()
        if ids:
            qs = qs.filter(pk__in=ids)
        headers = ["Mandat", "Debitor", "IBAN", "Typ", "Sequenz", "Signaturdatum", "Aktiv"]
        yield "\ufeff" + ";".join(headers) + "\r\n"
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
        for mandate in qs.iterator():
            yield _buffer_row(
                writer,
                buffer,
                [
                    mandate.mandate_reference,
                    mandate.debtor_name,
                    mandate.debtor_iban,
                    mandate.mandate_type,
                    mandate.sequence_type,
                    _de(mandate.signature_date),
                    "ja" if mandate.is_active else "nein",
                ],
            )

    elif dataset == "accounts":
        qs = BankAccount.objects.all()
        if ids:
            qs = qs.filter(pk__in=ids)
        headers = ["Konto", "Typ", "IBAN", "Bank", "Saldo", "Währung", "Letzter Sync"]
        yield "\ufeff" + ";".join(headers) + "\r\n"
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
        for account in qs.iterator():
            yield _buffer_row(
                writer,
                buffer,
                [
                    account.name,
                    account.get_account_type_display(),
                    account.iban,
                    account.bank_name,
                    _de(account.balance),
                    account.currency,
                    _de(account.last_sync_at),
                ],
            )

    else:
        raise ValueError(f"Unbekannter Export-Datensatz: {dataset}")
