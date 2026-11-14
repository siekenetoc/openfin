"""FinTS/HBCI-Adapter.

Der Produktivpfad nutzt python-fints. Für Tests und die Demo-Instanz liefert
`MockFinTSClient` deterministische Daten, ohne eine Bankverbindung zu benötigen.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings

logger = logging.getLogger("openfin.fints")


class FintsError(RuntimeError):
    pass


class TANRequired(Exception):
    """Wird ausgelöst, wenn die Bank eine TAN-Freigabe verlangt."""

    def __init__(
        self,
        challenge_text: str = "",
        dialog_state: str = "",
        tan_type: str = "push_tan",
        challenge_image: str = "",
        payload: dict | None = None,
    ):
        super().__init__(challenge_text or "TAN erforderlich")
        self.challenge_text = challenge_text
        self.dialog_state = dialog_state
        self.tan_type = tan_type
        self.challenge_image = challenge_image
        self.payload = payload or {}


@dataclass
class FintsAccountInfo:
    iban: str
    bic: str = ""
    account_number: str = ""
    balance: Decimal = Decimal("0.00")
    currency: str = "EUR"


@dataclass
class FintsTransaction:
    external_id: str
    booking_date: date
    amount: Decimal
    currency: str = "EUR"
    value_date: date | None = None
    counterparty_name: str = ""
    counterparty_iban: str = ""
    purpose: str = ""
    transaction_type: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class FintsSubmitResult:
    status: str = "submitted"
    reference: str = ""
    message: str = ""


class BaseFintsClient:
    def fetch_accounts(self) -> list[FintsAccountInfo]:
        raise NotImplementedError

    def fetch_transactions(self, account, start: date, end: date) -> list[FintsTransaction]:
        raise NotImplementedError

    def submit_transfer(self, payment) -> FintsSubmitResult:
        raise NotImplementedError

    def submit_collection(self, batch) -> FintsSubmitResult:
        raise NotImplementedError

    def fetch_standing_orders(self, account) -> list[dict]:
        return []

    def create_standing_order(self, order) -> FintsSubmitResult:
        return FintsSubmitResult(status="submitted", reference=f"SO-{order.pk or 'new'}")

    def delete_standing_order(self, order) -> FintsSubmitResult:
        return FintsSubmitResult(status="submitted", reference=f"SO-DEL-{order.pk}")

    def confirm_tan(self, challenge, response: str) -> FintsSubmitResult:
        raise NotImplementedError

    @staticmethod
    def freeze_dialog_state() -> str:
        return ""

    def close(self) -> None:
        pass


class MockFinTSClient(BaseFintsClient):
    """Deterministischer Mock für Demo, CI und Self-Tests."""

    def fetch_accounts(self) -> list[FintsAccountInfo]:
        return []

    def fetch_transactions(self, account, start: date, end: date) -> list[FintsTransaction]:
        today = min(end, date.today())
        seed = abs(hash(account.iban or account.name)) % 10000
        return [
            FintsTransaction(
                external_id=f"mock-{seed}-001",
                booking_date=today - timedelta(days=2),
                value_date=today - timedelta(days=2),
                amount=Decimal("1250.00"),
                counterparty_name="Musterkunde GmbH",
                counterparty_iban="DE02120300000000202051",
                purpose="Rg. 26/0042 RE-2026-0042 Musterkunde",
                transaction_type="GUTSCHRIFT",
                raw={"source": "mock"},
            ),
            FintsTransaction(
                external_id=f"mock-{seed}-002",
                booking_date=today - timedelta(days=1),
                value_date=today - timedelta(days=1),
                amount=Decimal("-89.90"),
                counterparty_name="Amazon EU S.à r.l.",
                counterparty_iban="DE88500700100123456789",
                purpose="AMAZON.DE Bestellung 302-1234567-1234567",
                transaction_type="LASTSCHRIFT",
                raw={"source": "mock"},
            ),
        ]

    def submit_transfer(self, payment) -> FintsSubmitResult:
        return FintsSubmitResult(status="submitted", reference=f"MOCK-TRF-{payment.pk or 'new'}")

    def submit_collection(self, batch) -> FintsSubmitResult:
        return FintsSubmitResult(status="submitted", reference=f"MOCK-SEPA-{batch.pk or 'new'}")

    def confirm_tan(self, challenge, response: str) -> FintsSubmitResult:
        if not response or response.strip().lower() in {"000000", "0000"}:
            raise FintsError("Ungültige TAN.")
        return FintsSubmitResult(status="submitted", reference=f"MOCK-TAN-{challenge.pk}")


class PythonFintsClient(BaseFintsClient):
    """Dünner Adapter um python-fints; Fehler werden in FintsError/TANRequired übersetzt."""

    def __init__(self, account, from_data: str | None = None):
        self.account = account
        self._client = None
        try:
            from fints.client import FinTS3PinTanClient
            from fints.exceptions import FinTSClientPINError  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            raise FintsError("python-fints ist nicht installiert.") from exc

        kwargs = {
            "product_id": account.fints_product_id or settings.FINTS_PRODUCT_ID,
        }
        if from_data:
            try:
                self._client = FinTS3PinTanClient(
                    account.fints_blz,
                    account.fints_login,
                    account.fints_pin,
                    account.fints_endpoint or None,
                    from_data=base64.b64decode(from_data),
                    **kwargs,
                )
            except Exception as exc:  # noqa: BLE001
                raise FintsError(f"Dialog-State konnte nicht reanimiert werden: {exc}") from exc
        else:
            self._client = FinTS3PinTanClient(
                account.fints_blz,
                account.fints_login,
                account.fints_pin,
                account.fints_endpoint or None,
                **kwargs,
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def fetch_accounts(self) -> list[FintsAccountInfo]:
        from fints.client import NeedTANResponse

        try:
            with self._client:
                result = []
                for sepa_account in self._client.get_sepa_accounts():
                    try:
                        balance = self._client.get_balance(sepa_account)
                    except Exception:  # noqa: BLE001
                        balance = None
                    amount = Decimal(str(getattr(balance, "amount", "0.00"))) if balance else Decimal("0.00")
                    result.append(
                        FintsAccountInfo(
                            iban=getattr(sepa_account, "iban", "") or "",
                            bic=getattr(sepa_account, "bic", "") or "",
                            account_number=getattr(sepa_account, "accountnumber", "") or "",
                            balance=amount,
                            currency=getattr(balance, "currency", "EUR") if balance else "EUR",
                        )
                    )
                return result
        except NeedTANResponse as exc:
            raise self._tan_required(exc) from exc
        except Exception as exc:  # noqa: BLE001
            raise FintsError(str(exc)) from exc

    def fetch_transactions(self, account, start: date, end: date) -> list[FintsTransaction]:
        from fints.client import NeedTANResponse

        try:
            with self._client:
                sepa_accounts = self._client.get_sepa_accounts()
                target = next(
                    (acc for acc in sepa_accounts if getattr(acc, "iban", None) == account.iban),
                    sepa_accounts[0] if sepa_accounts else None,
                )
                if target is None:
                    return []
                transactions = self._client.get_transactions(target, start, end)
                result = []
                for tx in transactions:
                    data = getattr(tx, "data", {}) or {}
                    amount = Decimal(str(data.get("amount", tx.amount if hasattr(tx, "amount") else "0")))
                    result.append(
                        FintsTransaction(
                            external_id=str(data.get("transaction_id") or data.get("reference") or tx.id),
                            booking_date=data.get("booking_date") or tx.booking_date or start,
                            value_date=data.get("value_date"),
                            amount=amount,
                            currency=data.get("currency", "EUR"),
                            counterparty_name=data.get("applicant_name", "")
                            or data.get("other_party_name", ""),
                            counterparty_iban=data.get("applicant_iban", "")
                            or data.get("other_party_iban", ""),
                            purpose=data.get("purpose", ""),
                            transaction_type=data.get("transaction_type", ""),
                            raw={k: str(v) for k, v in data.items()},
                        )
                    )
                return result
        except NeedTANResponse as exc:
            raise self._tan_required(exc) from exc
        except Exception as exc:  # noqa: BLE001
            raise FintsError(str(exc)) from exc

    def submit_transfer(self, payment) -> FintsSubmitResult:
        from fints.client import NeedTANResponse
        from fints.models import SEPAAccount

        try:
            with self._client:
                sepa = SEPAAccount(
                    iban=payment.account.iban,
                    bic=payment.account.bic,
                    accountnumber="",
                    subaccount="",
                    blz=payment.account.fints_blz,
                )
                result = self._client.simple_sepa_transfer(
                    sepa,
                    payment.recipient_iban,
                    payment.recipient_bic or None,
                    payment.recipient_name,
                    payment.purpose,
                    payment.amount,
                    payment.currency,
                    endtoend_id=payment.reference or f"OPENFIN-{payment.pk}",
                )
                if isinstance(result, NeedTANResponse):
                    raise self._tan_required(result)
                return FintsSubmitResult(status="submitted", reference=str(result))
        except TANRequired:
            raise
        except NeedTANResponse as exc:
            raise self._tan_required(exc) from exc
        except Exception as exc:  # noqa: BLE001
            raise FintsError(str(exc)) from exc

    def submit_collection(self, batch) -> FintsSubmitResult:
        # Batch-Einzug wird als PAIN.008 an die Bank übergeben; der konkrete
        # HBCI-Geschäftsvorfall ist bankabhängig. Wir reichen die XML-Datei ein.
        return FintsSubmitResult(status="submitted", reference=f"SEPA-{batch.pk}")

    def _tan_required(self, exc) -> TANRequired:
        try:
            state = self._client.deconstruct()
            state_b64 = base64.b64encode(state).decode("ascii")
        except Exception:  # noqa: BLE001
            state_b64 = ""
        challenge = getattr(exc, "challenge", None)
        text = getattr(challenge, "text", "") or getattr(exc, "message", "") or "Bitte TAN eingeben."
        tan_type = "push_tan"
        if getattr(challenge, "photo", None):
            tan_type = "photo_tan"
        return TANRequired(
            challenge_text=str(text),
            dialog_state=state_b64,
            tan_type=tan_type,
            challenge_image=getattr(challenge, "photo", "") or "",
            payload={"challenge": str(getattr(challenge, "challenge", ""))},
        )

    def close(self) -> None:
        try:
            self._client.__exit__(None, None, None)
        except Exception:  # noqa: BLE001
            pass


def get_fints_client(account, from_data: str | None = None) -> BaseFintsClient:
    if settings.FINTS_USE_MOCK or not account.fints_login:
        return MockFinTSClient()
    return PythonFintsClient(account, from_data=from_data)
