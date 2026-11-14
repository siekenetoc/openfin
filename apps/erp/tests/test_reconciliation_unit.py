from decimal import Decimal

import pytest

from apps.erp.reconciliation import extract_invoice_ids, normalize_purpose


def test_normalize_tippfehler_rechnungsnummer():
    assert normalize_purpose("Rg. 26/0042") == "RE-2026-0042"
    assert normalize_purpose("RECHNUNG NR. 26/42") == "RE-2026-0042"


def test_extract_invoice_ids():
    ids = extract_invoice_ids("Zahlung Rg. 26/0042 und RE-2026-0043")
    assert "RE-2026-0042" in ids
    assert "RE-2026-0043" in ids


def test_sql_guard_rejects_mutation():
    from apps.integrations.ai import LocalAIError, LocalAIClient

    with pytest.raises(LocalAIError):
        LocalAIClient._validate_sql("DELETE FROM banking_banktransaction", 100)
    with pytest.raises(LocalAIError):
        LocalAIClient._validate_sql("SELECT * FROM banking_banktransaction; DROP TABLE x", 100)


def test_sql_guard_adds_limit():
    from apps.integrations.ai import LocalAIClient

    sql = LocalAIClient._validate_sql("SELECT id, amount FROM banking_banktransaction", 50)
    assert sql.endswith("LIMIT 50")
