from datetime import date, timedelta

import pytest

from apps.banking.models import BankAccount, TANChallenge
from apps.banking.services.tan import confirm_tan_challenge, create_tan_challenge, expire_challenge
from apps.banking.services.fints_client import TANRequired


def make_account():
    return BankAccount.objects.create(
        name="TAN-Konto",
        account_type=BankAccount.AccountType.GIRO,
        provider=BankAccount.Provider.FINTS,
        iban="DE89370400440532013000",
        fints_login="demo",
    )


@pytest.mark.django_db
@pytest.mark.integration
def test_tan_confirm_with_mock(tenant_ctx):
    account = make_account()
    challenge = create_tan_challenge(
        account,
        "sync",
        TANRequired(challenge_text="Bitte TAN", dialog_state="ZmFrZQ=="),
    )
    account.refresh_from_db()
    assert account.needs_tan is True

    result = confirm_tan_challenge(challenge, "123456")
    assert result.status == TANChallenge.Status.CONFIRMED
    account.refresh_from_db()
    assert account.needs_tan is False


@pytest.mark.django_db
@pytest.mark.integration
def test_tan_rejects_invalid_response(tenant_ctx):
    account = make_account()
    challenge = create_tan_challenge(account, "sync", TANRequired("TAN bitte"))
    result = confirm_tan_challenge(challenge, "000000")
    assert result.status == TANChallenge.Status.FAILED
    assert result.error_message


@pytest.mark.django_db
@pytest.mark.integration
def test_expired_tan(tenant_ctx):
    account = make_account()
    challenge = TANChallenge.objects.create(
        account=account,
        operation="sync",
        challenge_text="alt",
        expires_at=__import__("django.utils.timezone", fromlist=["now"]).now() - timedelta(minutes=1),
    )
    result = confirm_tan_challenge(challenge, "123456")
    assert result.status == TANChallenge.Status.EXPIRED
