from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

from django.db.models import Q

from apps.banking.models import BankTransaction
from apps.erp.models import ReconciliationMatch

from .models import DATEVConfig

DATEV_COLUMNS = [
    "Umsatz",
    "Soll/Haben-Kennzeichen",
    "WKZ Umsatz",
    "Kurs",
    "Basis-Umsatz",
    "WKZ Basis-Umsatz",
    "Konto",
    "Gegenkonto",
    "BU-Schlüssel",
    "Belegdatum",
    "Belegfeld 1",
    "Belegfeld 2",
    "Skonto",
    "Buchungstext",
    "Postensperre",
    "Diverse Adressnummer",
    "Geschäftspartnerbank",
    "Sachverhalt",
    "Zinssperre",
    "Beleglink",
    "Beleginfo - Art 1",
    "Beleginfo - Inhalt 1",
    "Beleginfo - Art 2",
    "Beleginfo - Inhalt 2",
    "Beleginfo - Art 3",
    "Beleginfo - Inhalt 3",
    "Beleginfo - Art 4",
    "Beleginfo - Inhalt 4",
    "Beleginfo - Art 5",
    "Beleginfo - Inhalt 5",
    "Beleginfo - Art 6",
    "Beleginfo - Inhalt 6",
    "Beleginfo - Art 7",
    "Beleginfo - Inhalt 7",
    "Beleginfo - Art 8",
    "Beleginfo - Inhalt 8",
    "KOST1 - Kostenstelle",
    "KOST2 - Kostenstelle",
    "Kost-Menge",
    "EU-Land u. UStID",
    "EU-Steuersatz",
    "Abw. Versteuerungsart",
    "Sachkontenlänge",
    "Ergänzungsbilanz",
    "HYDRA-Konto",
    "Wirtschaftsjahr",
    "WJ-Beginn",
    "Auftragsnummer",
    "UStID des Mandanten",
    "Datum des Auftrags",
    "Bestellnummer",
    "Bank",
    "Buchungstext",
    "Datum Zahlungsziel",
]


def _header(config: DATEVConfig, date_from: date, date_to: date) -> list[str]:
    return [
        "EXTF",
        "700",
        "21",
        "Buchungsstapel",
        "13",
        date_from.strftime("%Y%m%d"),
        date_to.strftime("%Y%m%d"),
        str(config.fiscal_year),
        "1",
        "1",
        "0",
        "0",
        "EUR",
        "1",
        config.advisor_number,
        config.client_number,
        str(config.account_length),
        config.skr,
        "S",
        "0",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]


def build_extf_csv(config: DATEVConfig, date_from: date, date_to: date) -> str:
    transactions = (
        BankTransaction.objects.select_related("account")
        .filter(booking_date__gte=date_from, booking_date__lte=date_to)
        .filter(Q(status=BankTransaction.Status.AUTO_RECONCILED) | Q(status=BankTransaction.Status.MATCHED))
        .order_by("booking_date", "id")
    )
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(_header(config, date_from, date_to))
    writer.writerow(DATEV_COLUMNS)

    for tx in transactions:
        match = tx.reconciliation_matches.filter(
            status__in=[ReconciliationMatch.Status.AUTO, ReconciliationMatch.Status.CONFIRMED]
        ).first()
        invoice_ref = match.expected_payment.invoice_id if match and match.expected_payment else tx.erp_payment_reference
        skonto = match.discount_amount if match else Decimal("0.00")
        amount = abs(tx.amount)
        # Soll/Haben aus Sicht des Bankkontos: Zahlungseingang = Haben (H), Ausgabe = Soll (S)
        sh = "H" if tx.amount > 0 else "S"
        booking_text = (tx.purpose or tx.counterparty_name or "Bankumsatz")[:60]
        writer.writerow(
            [
                f"{amount:.2f}".replace(".", ","),
                sh,
                tx.currency,
                "",
                f"{amount:.2f}".replace(".", ","),
                tx.currency,
                config.default_credit_account if tx.amount > 0 else config.default_debit_account,
                config.default_debit_account if tx.amount > 0 else config.default_credit_account,
                "",
                tx.booking_date.strftime("%d%m"),
                (invoice_ref or "")[:36],
                tx.counterparty_name[:30],
                f"{skonto:.2f}".replace(".", ",") if skonto else "",
                booking_text,
            ]
            + [""] * (len(DATEV_COLUMNS) - 14)
        )
    return output.getvalue()


class DATEVOAuthClient:
    """Vorbereitete OAuth2-Schnittstelle für DATEV Buchungsdatenservice 1.0."""

    AUTH_URL = "https://login.datev.de/openidsandbox/authorize"
    TOKEN_URL = "https://login.datev.de/openidsandbox/token"

    def __init__(self, config: DATEVConfig):
        self.config = config

    def authorization_url(self, redirect_uri: str, state: str) -> str:
        from urllib.parse import urlencode

        query = urlencode(
            {
                "client_id": self.config.oauth_client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": "openid profile email",
                "state": state,
            }
        )
        return f"{self.AUTH_URL}?{query}"

    def upload_bookings(self, extf_csv: str) -> dict:
        raise NotImplementedError(
            "DATEV Buchungsdatenservice 1.0 erfordert eine freigeschaltete DATEV-Entwickler-App "
            "und ist als OAuth2-Integration vorbereitet."
        )
