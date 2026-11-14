from datetime import date, timedelta
from decimal import Decimal

import pytest
from lxml import etree

from apps.banking.models import BankAccount, OutgoingPayment
from apps.billing.models import SEPAMandate, SepaBatch, SepaBatchItem
from apps.billing.sepa import build_pain001, build_pain008

PAIN001 = "{urn:iso:std:iso:20022:tech:xsd:pain.001.001.03}"
PAIN008 = "{urn:iso:std:iso:20022:tech:xsd:pain.008.001.02}"


def test_build_pain001_valid_xml(tenant_ctx):
    account = BankAccount.objects.create(
        name="Auftragskonto",
        account_type=BankAccount.AccountType.GIRO,
        holder="OpenFin Demo GmbH",
        iban="DE89370400440532013000",
        bic="COBADEFFXXX",
    )
    payment = OutgoingPayment(
        account=account,
        payment_type=OutgoingPayment.PaymentType.SINGLE,
        recipient_name="Lieferant GmbH",
        recipient_iban="DE02120300000000202051",
        recipient_bic="BYLADEM1001",
        amount=Decimal("123.45"),
        currency="EUR",
        purpose="Rechnung RE-2026-0042",
        execution_date=date.today(),
    )
    xml = build_pain001(payment)
    root = etree.fromstring(xml.encode())
    assert root.tag == f"{PAIN001}Document"
    amount = root.find(f".//{PAIN001}InstdAmt")
    assert amount.text == "123.45"
    iban = root.find(f".//{PAIN001}CdtrAcct/{PAIN001}Id/{PAIN001}IBAN")
    assert iban.text == "DE02120300000000202051"


def test_build_pain008_valid_xml(tenant_ctx):
    account = BankAccount.objects.create(
        name="Gläubigerkonto",
        account_type=BankAccount.AccountType.GIRO,
        holder="OpenFin Demo GmbH",
        iban="DE89370400440532013000",
        bic="COBADEFFXXX",
    )
    mandate = SEPAMandate.objects.create(
        mandate_reference="MND-TEST-1",
        creditor_id="DE98ZZZ09999999999",
        creditor_name="OpenFin Demo GmbH",
        debtor_name="Debitor AG",
        debtor_iban="DE02120300000000202051",
        debtor_bic="BYLADEM1001",
        mandate_type=SEPAMandate.MandateType.CORE,
        sequence_type=SEPAMandate.SequenceType.FRST,
        signature_date=date.today() - timedelta(days=30),
    )
    batch = SepaBatch.objects.create(account=account, collection_date=date.today() + timedelta(days=5))
    SepaBatchItem.objects.create(
        batch=batch,
        mandate=mandate,
        amount=Decimal("49.99"),
        purpose="Rechnung RE-2026-0042",
    )
    xml = build_pain008(batch)
    root = etree.fromstring(xml.encode())
    assert root.tag == f"{PAIN008}Document"
    assert root.find(f".//{PAIN008}InstdAmt").text == "49.99"
    assert root.find(f".//{PAIN008}MndtId").text == "MND-TEST-1"
    assert root.find(f".//{PAIN008}ReqdColltnDt").text == batch.collection_date.strftime("%Y-%m-%d")


@pytest.mark.django_db
@pytest.mark.integration
def test_prenotification_sends_mail(tenant_ctx, mailoutbox):
    account = BankAccount.objects.create(
        name="Gläubigerkonto",
        account_type=BankAccount.AccountType.GIRO,
        holder="OpenFin Demo GmbH",
        iban="DE89370400440532013000",
    )
    mandate = SEPAMandate.objects.create(
        mandate_reference="MND-TEST-2",
        creditor_id="DE98ZZZ09999999999",
        creditor_name="OpenFin Demo GmbH",
        debtor_name="Debitor AG",
        debtor_iban="DE02120300000000202051",
        debtor_email="debitor@example.com",
        mandate_type=SEPAMandate.MandateType.CORE,
        sequence_type=SEPAMandate.SequenceType.RCUR,
        signature_date=date.today() - timedelta(days=10),
    )
    batch = SepaBatch.objects.create(account=account, collection_date=date.today() + timedelta(days=5))
    item = SepaBatchItem.objects.create(batch=batch, mandate=mandate, amount=Decimal("10.00"), purpose="Test")
    from apps.billing.services import send_prenotification

    assert send_prenotification(item) is True
    assert len(mailoutbox) == 1
    assert "MND-TEST-2" in mailoutbox[0].body
