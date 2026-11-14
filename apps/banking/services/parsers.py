"""MT940- und CAMT.053-Parser für Kontoauszüge."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree as SafeET

CAMT_NS = {
    "c": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02",
    "c8": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.08",
}


def _text(node, path: str, default: str = "") -> str:
    found = node.find(path, CAMT_NS)
    return found.text.strip() if found is not None and found.text else default


def _dec(value: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return Decimal("0.00")


def parse_mt940(text: str) -> list[dict]:
    """Parst MT940 über die mt-940-Bibliothek; Fallback ist ein toleranter Regex-Parser."""
    try:
        from mt940 import parse

        statement = parse(text)
        results = []
        for tx in statement.transactions:
            results.append(
                {
                    "external_id": getattr(tx, "id", None) or f"mt940-{tx.date}-{tx.amount}",
                    "booking_date": tx.date,
                    "value_date": getattr(tx, "guessed_entry_date", None) or tx.date,
                    "amount": Decimal(str(tx.amount)),
                    "currency": "EUR",
                    "counterparty_name": getattr(tx, "counterparty_name", "") or "",
                    "counterparty_iban": getattr(tx, "counterparty_iban", "") or "",
                    "purpose": getattr(tx, "purpose", "") or "",
                    "transaction_type": getattr(tx, "status", "") or "",
                }
            )
        return results
    except Exception:  # noqa: BLE001
        return _parse_mt940_fallback(text)


def _parse_mt940_fallback(text: str) -> list[dict]:
    import re

    results = []
    current: dict = {}
    for line in text.splitlines():
        if line.startswith(":61:"):
            if current:
                results.append(current)
            match = re.search(r"(\d{6})\s*(C|D|CR|DR)\s*([\d,\.]+)", line)
            if match:
                yy, mm, dd = match.group(1)[:2], match.group(1)[2:4], match.group(1)[4:6]
                amount = _dec(match.group(3).replace(".", "").replace(",", "."))
                if match.group(2).upper() in {"D", "DR"}:
                    amount = -amount
                current = {
                    "external_id": f"mt940-{match.group(1)}-{amount}-{len(results)}",
                    "booking_date": date(2000 + int(yy), int(mm), int(dd)),
                    "value_date": None,
                    "amount": amount,
                    "currency": "EUR",
                    "counterparty_name": "",
                    "counterparty_iban": "",
                    "purpose": "",
                    "transaction_type": match.group(2),
                }
        elif line.startswith(":86:") and current:
            current["purpose"] = line[4:].strip()
            import re as _re

            iban = _re.search(r"(DE\d{20})", current["purpose"])
            if iban:
                current["counterparty_iban"] = iban.group(1)
    if current:
        results.append(current)
    return results


def parse_camt053(xml_bytes: bytes | str) -> list[dict]:
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode("utf-8")
    root = SafeET.fromstring(xml_bytes)
    results: list[dict] = []

    # Namespace tolerant: unabhängig von der CAMT-Version nach den Elementen suchen.
    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    entries = [el for el in root.iter() if local(el.tag) == "Ntry"]
    for index, entry in enumerate(entries):
        def child(name: str):
            return next((el for el in entry.iter() if local(el.tag) == name), None)

        amount_el = child("Amt")
        indicator_el = child("CdtDbtInd")
        amount = _dec(amount_el.text if amount_el is not None else "0")
        if indicator_el is not None and indicator_el.text == "DBIT":
            amount = -amount

        booking_el = child("BookgDt") or child("ValDt")
        booking_date = date.today()
        if booking_el is not None:
            date_el = next((el for el in booking_el.iter() if local(el.tag) in {"Dt", "DtTm"}), None)
            if date_el is not None and date_el.text:
                raw = date_el.text[:10]
                try:
                    booking_date = datetime.strptime(raw, "%Y-%m-%d").date()
                except ValueError:
                    try:
                        booking_date = datetime.strptime(raw, "%Y%m%d").date()
                    except ValueError:
                        pass

        def text_of(name: str) -> str:
            el = child(name)
            return el.text.strip() if el is not None and el.text else ""

        ref = text_of("AcctSvcrRef") or text_of("EndToEndId") or text_of("TxId") or f"camt-{index}"
        results.append(
            {
                "external_id": ref,
                "booking_date": booking_date,
                "value_date": None,
                "amount": amount,
                "currency": "EUR",
                "counterparty_name": text_of("Nm"),
                "counterparty_iban": text_of("IBAN"),
                "purpose": text_of("Ustrd") or text_of("AddtlNtryInf"),
                "transaction_type": text_of("CdtDbtInd"),
            }
        )
    return results
