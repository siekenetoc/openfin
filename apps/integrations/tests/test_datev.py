from datetime import date
from decimal import Decimal

import pytest

from apps.banking.models import BankAccount, BankTransaction
from apps.integrations.datev import DATEV_COLUMNS, build_extf_csv
from apps.integrations.models import DATEVConfig


@pytest.mark.django_db
@pytest.mark.integration
def test_extf_export_has_bom_and_semicolons(tenant_ctx):
    account = BankAccount.objects.create(
        name="Bank",
        account_type=BankAccount.AccountType.GIRO,
        iban="DE89370400440532013000",
    )
    BankTransaction.objects.create(
        account=account,
        external_id="datev-1",
        booking_date=date.today(),
        amount=Decimal("100.00"),
        counterparty_name="Kunde AG",
        purpose="Rechnung RE-2026-0042",
        status=BankTransaction.Status.MATCHED,
    )
    config = DATEVConfig(advisor_number="12345", client_number="67890", fiscal_year=2026)
    content = build_extf_csv(config, date.today(), date.today())
    assert content.startswith("\ufeff")
    lines = content.splitlines()
    assert lines[0].startswith("EXTF;700;21;Buchungsstapel")
    assert "Umsatz;Soll/Haben-Kennzeichen" in lines[1]
    assert len(lines) == 3
    assert lines[2].startswith("100,00;H;EUR")
    assert len(DATEV_COLUMNS) >= 50
