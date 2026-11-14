from __future__ import annotations

import logging

from celery import shared_task
from django.db import connection
from django_tenants.utils import schema_context, tenant_context

from apps.core.models import Tenant

logger = logging.getLogger("openfin.tasks.banking")


def _tenant(schema_name: str) -> Tenant:
    with schema_context("public"):
        return Tenant.objects.get(schema_name=schema_name)


@shared_task(bind=True, max_retries=3)
def sync_bank_account(self, schema_name: str, account_id: int):
    from apps.banking.models import BankAccount
    from apps.banking.services.sync import sync_account

    tenant = _tenant(schema_name)
    with tenant_context(tenant):
        account = BankAccount.objects.filter(pk=account_id, is_active=True).first()
        if not account:
            return {"status": "missing"}
        result = sync_account(account)
        return result


@shared_task
def sync_all_accounts():
    from apps.banking.models import BankAccount

    with schema_context("public"):
        tenants = list(Tenant.objects.filter(is_active=True))
    dispatched = 0
    for tenant in tenants:
        with tenant_context(tenant):
            for account in BankAccount.objects.filter(is_active=True, provider=BankAccount.Provider.FINTS):
                sync_bank_account.delay(tenant.schema_name, account.pk)
                dispatched += 1
    return {"dispatched": dispatched}


@shared_task(bind=True, max_retries=2)
def submit_outgoing_payment(self, schema_name: str, payment_id: int):
    from apps.banking.models import OutgoingPayment
    from apps.banking.services.fints_client import FintsError, TANRequired, get_fints_client
    from apps.banking.services.tan import create_tan_challenge
    from apps.billing.sepa import build_pain001

    tenant = _tenant(schema_name)
    with tenant_context(tenant):
        payment = OutgoingPayment.objects.filter(pk=payment_id).first()
        if not payment:
            return {"status": "missing"}
        payment.pain_xml = build_pain001(payment, tenant=tenant)
        payment.save(update_fields=["pain_xml"])
        client = get_fints_client(payment.account)
        try:
            result = client.submit_transfer(payment)
            payment.status = OutgoingPayment.Status.SUBMITTED
            payment.error_message = ""
            payment.save(update_fields=["status", "error_message"])
            return {"status": result.status, "reference": result.reference}
        except TANRequired as exc:
            challenge = create_tan_challenge(
                payment.account,
                "payment",
                exc,
                payload={"payment_id": payment.pk},
            )
            payment.status = OutgoingPayment.Status.PENDING_TAN
            payment.tan_challenge = challenge
            payment.save(update_fields=["status", "tan_challenge"])
            return {"status": "pending_tan", "challenge_id": challenge.pk}
        except FintsError as exc:
            payment.status = OutgoingPayment.Status.FAILED
            payment.error_message = str(exc)
            payment.save(update_fields=["status", "error_message"])
            return {"status": "error", "message": str(exc)}
        finally:
            client.close()


@shared_task
def submit_sepa_batch(schema_name: str, batch_id: int):
    from apps.banking.services.fints_client import get_fints_client
    from apps.billing.models import SepaBatch
    from apps.billing.sepa import build_pain008

    tenant = _tenant(schema_name)
    with tenant_context(tenant):
        batch = SepaBatch.objects.filter(pk=batch_id).first()
        if not batch:
            return {"status": "missing"}
        batch.xml_file = build_pain008(batch, tenant=tenant)
        batch.save(update_fields=["xml_file"])
        client = get_fints_client(batch.account)
        try:
            result = client.submit_collection(batch)
            batch.status = SepaBatch.Status.SUBMITTED
            batch.save(update_fields=["status"])
            return {"status": result.status, "reference": result.reference}
        finally:
            client.close()


def current_schema() -> str:
    return getattr(connection, "schema_name", "public")
