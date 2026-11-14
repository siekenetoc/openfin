"""SEPA-XML-Generatoren für PAIN.001.001.03 (Überweisung) und PAIN.008.001.02 (Einzug)."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from lxml import etree

PAIN001_NS = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
PAIN008_NS = "urn:iso:std:iso:20022:tech:xsd:pain.008.001.02"

IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")


def _validate_iban(iban: str) -> str:
    cleaned = (iban or "").replace(" ", "").upper()
    if not IBAN_RE.match(cleaned):
        raise ValueError(f"Ungültige IBAN: {iban!r}")
    return cleaned


def _sub(parent, tag: str, text: str | None = None, ns: str = PAIN001_NS):
    el = etree.SubElement(parent, f"{{{ns}}}{tag}")
    if text is not None:
        el.text = str(text)
    return el


def _money(amount: Decimal) -> str:
    return f"{Decimal(amount):.2f}"


def _date(value: date | datetime | None) -> str:
    return (value or date.today()).strftime("%Y-%m-%d")


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def build_pain001(payment, tenant=None) -> str:
    ns = PAIN001_NS
    root = etree.Element(f"{{{ns}}}Document", nsmap={None: ns})
    body = _sub(root, "CstmrCdtTrfInitn", ns=ns)
    header = _sub(body, "GrpHdr", ns=ns)

    message_id = f"MSG-{uuid4().hex[:20].upper()}"
    _sub(header, "MsgId", message_id, ns)
    _sub(header, "CreDtTm", _timestamp(), ns)
    _sub(header, "NbOfTxs", "1", ns)
    _sub(header, "CtrlSum", _money(payment.amount), ns)

    initg_party = _sub(header, "InitgPty", ns)
    _sub(initg_party, "Nm", payment.account.holder or payment.account.name, ns)

    pmt_info = _sub(body, "PmtInf", ns)
    _sub(pmt_info, "PmtInfId", f"PMT-{uuid4().hex[:16].upper()}", ns)
    _sub(pmt_info, "PmtMtd", "TRF", ns)
    _sub(pmt_info, "BtchBookg", "false", ns)
    _sub(pmt_info, "NbOfTxs", "1", ns)
    _sub(pmt_info, "CtrlSum", _money(payment.amount), ns)
    pmt_type = _sub(pmt_info, "PmtTpInf", ns)
    _sub(pmt_type, "SvcLvl", ns=ns)
    svc = pmt_type.find(f"{{{ns}}}SvcLvl")
    _sub(svc, "Cd", "SEPA", ns)
    if payment.payment_type == payment.PaymentType.INSTANT:
        _sub(pmt_type, "LclInstrm", ns=ns)
        lcl = pmt_type.find(f"{{{ns}}}LclInstrm")
        _sub(lcl, "Cd", "INST", ns)
    _sub(pmt_info, "ReqdExctnDt", _date(payment.execution_date), ns)

    debtor = _sub(pmt_info, "Dbtr", ns)
    _sub(debtor, "Nm", payment.account.holder or payment.account.name, ns)
    debtor_account = _sub(pmt_info, "DbtrAcct", ns)
    _sub(debtor_account, "Id", ns=ns)
    _sub(debtor_account.find(f"{{{ns}}}Id"), "IBAN", _validate_iban(payment.account.iban), ns)
    if payment.account.bic:
        debtor_agent = _sub(pmt_info, "DbtrAgt", ns)
        _sub(debtor_agent, "FinInstnId", ns=ns)
        _sub(debtor_agent.find(f"{{{ns}}}FinInstnId"), "BIC", payment.account.bic, ns)

    tx = _sub(pmt_info, "CdtTrfTxInf", ns)
    pmt_id = _sub(tx, "PmtId", ns)
    _sub(pmt_id, "EndToEndId", payment.reference or f"OPENFIN-{payment.pk or uuid4().hex[:8]}", ns)
    amount = _sub(tx, "Amt", ns)
    _sub(amount, "InstdAmt", _money(payment.amount), ns).set("Ccy", payment.currency)
    if payment.recipient_bic:
        creditor_agent = _sub(tx, "CdtrAgt", ns)
        _sub(creditor_agent, "FinInstnId", ns=ns)
        _sub(creditor_agent.find(f"{{{ns}}}FinInstnId"), "BIC", payment.recipient_bic, ns)
    creditor = _sub(tx, "Cdtr", ns)
    _sub(creditor, "Nm", payment.recipient_name, ns)
    creditor_account = _sub(tx, "CdtrAcct", ns)
    _sub(creditor_account, "Id", ns=ns)
    _sub(creditor_account.find(f"{{{ns}}}Id"), "IBAN", _validate_iban(payment.recipient_iban), ns)
    remittance = _sub(tx, "RmtInf", ns)
    _sub(remittance, "Ustrd", payment.purpose[:140], ns)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True).decode("utf-8")


def build_pain008(batch, tenant=None) -> str:
    ns = PAIN008_NS
    items = list(batch.items.select_related("mandate").all())
    if not items:
        raise ValueError("SEPA-Batch enthält keine Einzüge.")
    total = sum((item.amount for item in items), Decimal("0.00"))

    root = etree.Element(f"{{{ns}}}Document", nsmap={None: ns})
    body = _sub(root, "CstmrDrctDbtInitn", ns=ns)
    header = _sub(body, "GrpHdr", ns=ns)
    _sub(header, "MsgId", batch.message_id, ns)
    _sub(header, "CreDtTm", _timestamp(), ns)
    _sub(header, "NbOfTxs", str(len(items)), ns)
    _sub(header, "CtrlSum", _money(total), ns)
    initg = _sub(header, "InitgPty", ns)
    _sub(initg, "Nm", batch.account.holder or batch.account.name, ns)

    by_type: dict[str, list] = {}
    for item in items:
        by_type.setdefault(item.mandate.mandate_type, []).append(item)

    for mandate_type, group in by_type.items():
        group_total = sum((item.amount for item in group), Decimal("0.00"))
        pmt_info = _sub(body, "PmtInf", ns)
        _sub(pmt_info, "PmtInfId", f"PMT-{uuid4().hex[:16].upper()}", ns)
        _sub(pmt_info, "PmtMtd", "DD", ns)
        _sub(pmt_info, "BtchBookg", "false", ns)
        _sub(pmt_info, "NbOfTxs", str(len(group)), ns)
        _sub(pmt_info, "CtrlSum", _money(group_total), ns)
        pmt_type = _sub(pmt_info, "PmtTpInf", ns)
        svc = _sub(pmt_type, "SvcLvl", ns=ns)
        _sub(svc, "Cd", "SEPA", ns)
        lcl = _sub(pmt_type, "LclInstrm", ns=ns)
        _sub(lcl, "Cd", mandate_type, ns)
        _sub(pmt_type, "SeqTp", group[0].mandate.sequence_type, ns)
        _sub(pmt_info, "ReqdColltnDt", _date(batch.collection_date), ns)

        creditor = _sub(pmt_info, "Cdtr", ns)
        _sub(creditor, "Nm", batch.account.holder or batch.account.name, ns)
        creditor_account = _sub(pmt_info, "CdtrAcct", ns)
        _sub(creditor_account, "Id", ns=ns)
        _sub(creditor_account.find(f"{{{ns}}}Id"), "IBAN", _validate_iban(batch.account.iban), ns)
        if batch.account.bic:
            creditor_agent = _sub(pmt_info, "CdtrAgt", ns)
            _sub(creditor_agent, "FinInstnId", ns=ns)
            _sub(creditor_agent.find(f"{{{ns}}}FinInstnId"), "BIC", batch.account.bic, ns)
        _sub(pmt_info, "ChrgBr", "SLEV", ns)
        creditor_scheme = _sub(pmt_info, "CdtrSchmeId", ns)
        _sub(creditor_scheme, "Id", ns=ns)
        private_id = _sub(creditor_scheme.find(f"{{{ns}}}Id"), "PrvtId", ns=ns)
        other = _sub(private_id, "Othr", ns=ns)
        _sub(other, "Id", group[0].mandate.creditor_id, ns)
        scheme = _sub(other, "SchmeNm", ns=ns)
        _sub(scheme, "Prtry", "SEPA", ns)

        for item in group:
            tx = _sub(pmt_info, "DrctDbtTxInf", ns)
            pmt_id = _sub(tx, "PmtId", ns)
            _sub(pmt_id, "EndToEndId", item.end_to_end_id, ns)
            amount = _sub(tx, "InstdAmt", _money(item.amount), ns)
            amount.set("Ccy", "EUR")
            mandate = _sub(tx, "DrctDbtTx", ns)
            mandate_info = _sub(mandate, "MndtRltdInf", ns)
            _sub(mandate_info, "MndtId", item.mandate.mandate_reference, ns)
            _sub(mandate_info, "DtOfSgntr", _date(item.mandate.signature_date), ns)
            _sub(mandate_info, "AmdmntInd", "false", ns)
            debtor_agent = _sub(tx, "DbtrAgt", ns)
            _sub(debtor_agent, "FinInstnId", ns=ns)
            if item.mandate.debtor_bic:
                _sub(debtor_agent.find(f"{{{ns}}}FinInstnId"), "BIC", item.mandate.debtor_bic, ns)
            else:
                _sub(debtor_agent.find(f"{{{ns}}}FinInstnId"), "Othr", ns=ns)
                other_fi = debtor_agent.find(f"{{{ns}}}FinInstnId").find(f"{{{ns}}}Othr")
                _sub(other_fi, "Id", "NOTPROVIDED", ns)
            debtor = _sub(tx, "Dbtr", ns)
            _sub(debtor, "Nm", item.mandate.debtor_name, ns)
            debtor_account = _sub(tx, "DbtrAcct", ns)
            _sub(debtor_account, "Id", ns=ns)
            _sub(debtor_account.find(f"{{{ns}}}Id"), "IBAN", _validate_iban(item.mandate.debtor_iban), ns)
            remittance = _sub(tx, "RmtInf", ns)
            _sub(remittance, "Ustrd", item.purpose[:140], ns)

    batch.total_amount = total
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True).decode("utf-8")
