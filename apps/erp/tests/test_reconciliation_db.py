from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.banking.models import BankAccount, BankTransaction
from apps.erp.models import ERPConfig, ExpectedPayment, ReconciliationMatch
from apps.erp.reconciliation import reconcile_transaction

TODAY = date.today()


def make_account():
    return BankAccount.objects.create(
        name="Testkonto",
        account_type=BankAccount.AccountType.GIRO,
        provider=BankAccount.Provider.FINTS,
        iban="DE89370400440532013000",
        bic="COBADEFFXXX",
        fints_login="demo",
    )


def make_config(account):
    return ERPConfig.objects.create(
        name="Test ERP",
        erp_base_url="http://erp.local",
        default_bank_account=account,
        default_discount_rate=Decimal("2.00"),
        default_discount_days=10,
    )


def make_payment(config, invoice_id, customer, iban, amount, due_days=10):
    return ExpectedPayment.objects.create(
        erp_config=config,
        erp_name=invoice_id,
        invoice_id=invoice_id,
        customer_name=customer,
        customer_iban=iban,
        amount=amount,
        issue_date=TODAY - timedelta(days=5),
        due_date=TODAY + timedelta(days=due_days),
        description=f"Rechnung {invoice_id}",
    )


def make_tx(account, external_id, amount, customer, iban, purpose):
    return BankTransaction.objects.create(
        account=account,
        external_id=external_id,
        booking_date=TODAY,
        amount=amount,
        counterparty_name=customer,
        counterparty_iban=iban,
        purpose=purpose,
    )


@pytest.mark.django_db
@pytest.mark.integration
def test_exact_match_is_auto_reconciled(tenant_ctx):
    account = make_account()
    config = make_config(account)
    payment = make_payment(config, "RE-2026-0042", "Musterkunde GmbH", "DE02120300000000202051", Decimal("1250.00"))
    tx = make_tx(account, "t1", Decimal("1250.00"), "Musterkunde GmbH", "DE02120300000000202051", "Rg. 26/0042")

    result = reconcile_transaction(tx)
    tx.refresh_from_db()
    payment.refresh_from_db()

    assert result["status"] == BankTransaction.Status.AUTO_RECONCILED
    assert tx.confidence_score > 95
    assert payment.status == ExpectedPayment.Status.PAID
    match = tx.reconciliation_matches.get()
    assert match.erp_payment_entry.startswith("MOCK-PE-")


@pytest.mark.django_db
@pytest.mark.integration
def test_skonto_match_with_deduction(tenant_ctx):
    account = make_account()
    config = make_config(account)
    payment = make_payment(config, "RE-2026-0050", "Skonto AG", "DE44500105175407324931", Decimal("1000.00"), due_days=20)
    tx = make_tx(account, "t2", Decimal("980.00"), "Skonto AG", "DE44500105175407324931", "Rechnung 26/0050")

    result = reconcile_transaction(tx)
    match = ReconciliationMatch.objects.get(transaction=tx)

    assert result["status"] == BankTransaction.Status.AUTO_RECONCILED
    assert match.stage == ReconciliationMatch.Stage.SKONTO
    assert match.discount_amount == Decimal("20.00")
    assert match.deductions
    payment.refresh_from_db()
    assert payment.status == ExpectedPayment.Status.PAID


@pytest.mark.django_db
@pytest.mark.integration
def test_rounding_difference_needs_review(tenant_ctx):
    account = make_account()
    config = make_config(account)
    make_payment(config, "RE-2026-0060", "Rundung AG", "DE75512108001245126199", Decimal("3400.00"))
    tx = make_tx(account, "t3", Decimal("3399.00"), "Rundung AG", "DE75512108001245126199", "Rechnung 26/0060")

    result = reconcile_transaction(tx)
    tx.refresh_from_db()

    assert result["status"] == BankTransaction.Status.NEEDS_REVIEW
    assert 50 <= tx.confidence_score <= 95
    assert tx.reconciliation_matches.filter(status=ReconciliationMatch.Status.PROPOSED).exists()


@pytest.mark.django_db
@pytest.mark.integration
def test_subset_sum_collective_transfer(tenant_ctx):
    account = make_account()
    config = make_config(account)
    customer = "Sammel AG"
    iban = "DE02120300000000202051"
    p1 = make_payment(config, "RE-2026-0101", customer, iban, Decimal("500.00"))
    p2 = make_payment(config, "RE-2026-0102", customer, iban, Decimal("300.00"))
    p3 = make_payment(config, "RE-2026-0103", customer, iban, Decimal("200.00"))
    tx = make_tx(account, "t4", Decimal("1000.00"), customer, iban, "Sammelzahlung")

    result = reconcile_transaction(tx)
    match = ReconciliationMatch.objects.get(transaction=tx)

    assert result["status"] == BankTransaction.Status.AUTO_RECONCILED
    assert match.stage == ReconciliationMatch.Stage.SUBSET
    assert len(match.references) == 3
    for payment in [p1, p2, p3]:
        payment.refresh_from_db()
        assert payment.status == ExpectedPayment.Status.PAID


@pytest.mark.django_db
@pytest.mark.integration
def test_approve_review_match(tenant_ctx):
    from apps.erp.reconciliation import approve_match

    account = make_account()
    config = make_config(account)
    payment = make_payment(config, "RE-2026-0070", "Review AG", "DE44500105175407324931", Decimal("1000.00"))
    tx = make_tx(account, "t5", Decimal("999.00"), "Review AG", "DE44500105175407324931", "Rechnung 26/0070")
    reconcile_transaction(tx)
    match = tx.reconciliation_matches.get()

    approve_match(match)
    tx.refresh_from_db()
    payment.refresh_from_db()
    assert tx.status == BankTransaction.Status.MATCHED
    assert payment.status in {ExpectedPayment.Status.PAID, ExpectedPayment.Status.PARTIAL}
