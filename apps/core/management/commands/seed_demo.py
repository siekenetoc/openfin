from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.banking.models import BankAccount, BankTransaction, CategoryRule, TANChallenge
from apps.billing.models import PaymentProviderConfig, SEPAMandate
from apps.billing.services import create_payment_link
from apps.erp.models import ERPConfig, ExpectedPayment
from apps.erp.reconciliation import reconcile_transaction
from apps.integrations.models import DATEVConfig
from apps.providers.models import DepotPosition


class Command(BaseCommand):
    help = "Seeded Demo-Daten im aktuellen Tenant-Schema."

    def handle(self, *args, **options):
        today = date.today()
        business, _ = BankAccount.objects.get_or_create(
            name="Geschäftskonto",
            defaults={
                "account_type": BankAccount.AccountType.GIRO,
                "provider": BankAccount.Provider.FINTS,
                "bank_name": "Demo Bank",
                "holder": "OpenFin Demo GmbH",
                "iban": "DE89370400440532013000",
                "bic": "COBADEFFXXX",
                "balance": Decimal("24500.00"),
                "fints_blz": "37040044",
                "fints_login": "demo",
                "fints_endpoint": "https://banking-demo.de/fints",
                "fints_pin": "12345",
            },
        )
        paypal, _ = BankAccount.objects.get_or_create(
            name="PayPal Wallet",
            defaults={
                "account_type": BankAccount.AccountType.WALLET,
                "provider": BankAccount.Provider.PAYPAL,
                "holder": "OpenFin Demo GmbH",
                "balance": Decimal("850.00"),
                "credentials": {"mode": "sandbox"},
            },
        )
        depot, _ = BankAccount.objects.get_or_create(
            name="Wertpapierdepot",
            defaults={
                "account_type": BankAccount.AccountType.DEPOT,
                "provider": BankAccount.Provider.MANUAL,
                "holder": "OpenFin Demo GmbH",
                "balance": Decimal("0.00"),
            },
        )

        for rule in [
            ("Amazon Einkauf", r"amazon", "Einkauf / Material", "Einkauf", 10),
            ("Miete", r"miete", "Raumkosten", "Verwaltung", 20),
            ("Telekom", r"telekom|1&1|vodafone", "Telefon / Internet", "IT", 30),
            ("Umsatzerlöse", r"rechnung|rg\.", "Umsatzerlöse", "Vertrieb", 50),
        ]:
            CategoryRule.objects.get_or_create(
                name=rule[0],
                defaults={"pattern": rule[1], "category": rule[2], "cost_center": rule[3], "priority": rule[4]},
            )

        erp, _ = ERPConfig.objects.get_or_create(
            name="ERPNext Demo",
            defaults={
                "erp_base_url": "http://erpnext.local:8080",
                "company": "OpenFin Demo GmbH",
                "default_bank_account": business,
                "default_discount_rate": Decimal("2.00"),
                "default_discount_days": 10,
            },
        )

        expected_specs = [
            ("RE-2026-0042", "Musterkunde GmbH", "DE02120300000000202051", Decimal("1250.00"), 5),
            ("RE-2026-0043", "Beispiel AG", "DE44500105175407324931", Decimal("3400.00"), 12),
            ("RE-2026-0044", "Nordlicht Handel", "DE75512108001245126199", Decimal("780.50"), 20),
        ]
        for invoice_id, customer, iban, amount, due_days in expected_specs:
            ExpectedPayment.objects.get_or_create(
                invoice_id=invoice_id,
                defaults={
                    "erp_config": erp,
                    "erp_name": invoice_id,
                    "customer_name": customer,
                    "customer_iban": iban,
                    "amount": amount,
                    "issue_date": today - timedelta(days=10),
                    "due_date": today + timedelta(days=due_days),
                    "description": f"Rechnung {invoice_id}",
                },
            )

        SEPAMandate.objects.get_or_create(
            mandate_reference="MND-2026-0001",
            defaults={
                "creditor_id": "DE98ZZZ09999999999",
                "creditor_name": "OpenFin Demo GmbH",
                "debtor_name": "Musterkunde GmbH",
                "debtor_iban": "DE02120300000000202051",
                "debtor_bic": "BYLADEM1001",
                "debtor_email": "buchhaltung@musterkunde.example",
                "customer_ref": "Musterkunde GmbH",
                "mandate_type": SEPAMandate.MandateType.CORE,
                "sequence_type": SEPAMandate.SequenceType.FRST,
                "signature_date": today - timedelta(days=60),
            },
        )
        SEPAMandate.objects.get_or_create(
            mandate_reference="MND-2026-0002",
            defaults={
                "creditor_id": "DE98ZZZ09999999999",
                "creditor_name": "OpenFin Demo GmbH",
                "debtor_name": "Nordlicht Handel",
                "debtor_iban": "DE75512108001245126199",
                "debtor_email": "finance@nordlicht.example",
                "customer_ref": "Nordlicht Handel",
                "mandate_type": SEPAMandate.MandateType.B2B,
                "sequence_type": SEPAMandate.SequenceType.RCUR,
                "signature_date": today - timedelta(days=120),
            },
        )

        DepotPosition.objects.get_or_create(
            account=depot,
            isin="DE0007164600",
            defaults={"name": "SAP SE", "quantity": Decimal("12.000000"), "price": Decimal("142.3000"), "yahoo_symbol": "SAP.DE"},
        )
        DepotPosition.objects.get_or_create(
            account=depot,
            isin="IE00B4L5Y983",
            defaults={"name": "iShares Core MSCI World", "quantity": Decimal("40.000000"), "price": Decimal("92.1500"), "yahoo_symbol": "IWDA.AS"},
        )

        DATEVConfig.objects.get_or_create(
            advisor_number="12345",
            client_number="67890",
            defaults={"fiscal_year": today.year, "skr": "04", "is_active": True},
        )
        for provider in ["stripe", "paypal", "wero"]:
            PaymentProviderConfig.objects.get_or_create(
                provider=provider,
                defaults={"mode": "sandbox", "is_active": True},
            )

        # Demo-Umsätze: ein Auto-Match (Skonto) und ein Triage-Fall.
        tx1, created1 = BankTransaction.objects.get_or_create(
            account=business,
            external_id="demo-2026-0042",
            defaults={
                "booking_date": today - timedelta(days=2),
                "value_date": today - timedelta(days=2),
                "amount": Decimal("1225.00"),
                "currency": "EUR",
                "counterparty_name": "Musterkunde GmbH",
                "counterparty_iban": "DE02120300000000202051",
                "purpose": "Rg. 26/0042 Musterkunde",
                "transaction_type": "GUTSCHRIFT",
            },
        )
        tx2, created2 = BankTransaction.objects.get_or_create(
            account=business,
            external_id="demo-2026-0043",
            defaults={
                "booking_date": today - timedelta(days=1),
                "value_date": today - timedelta(days=1),
                "amount": Decimal("3399.00"),
                "currency": "EUR",
                "counterparty_name": "Beispiel AG",
                "counterparty_iban": "DE44500105175407324931",
                "purpose": "Rechnung 26/0043",
                "transaction_type": "GUTSCHRIFT",
            },
        )
        if created1:
            reconcile_transaction(tx1)
        if created2:
            reconcile_transaction(tx2)

        # Demo-Payment-Link (Wero-QR lokal erzeugt).
        first_open = ExpectedPayment.objects.filter(status=ExpectedPayment.Status.OPEN).first()
        if first_open:
            create_payment_link(first_open, "wero")

        # Demo-TAN-Freigabe (Mock akzeptiert jede 6-stellige TAN).
        if not TANChallenge.objects.filter(status=TANChallenge.Status.PENDING).exists():
            TANChallenge.objects.create(
                account=business,
                operation="sync",
                tan_type=TANChallenge.TANType.PUSH,
                challenge_text="Demo: Bitte geben Sie eine 6-stellige TAN ein (z. B. 123456).",
                expires_at=timezone.now() + timedelta(minutes=30),
            )

        self.stdout.write(self.style.SUCCESS("Demo-Daten angelegt."))
