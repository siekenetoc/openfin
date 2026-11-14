from __future__ import annotations

import logging
from datetime import date, timedelta

from celery import shared_task
from django.conf import settings
from django_tenants.utils import schema_context, tenant_context

from apps.core.models import Tenant

logger = logging.getLogger("openfin.tasks.billing")


@shared_task
def send_due_prenotifications():
    from apps.billing.models import SepaBatch
    from apps.billing.services import send_prenotifications_for_batch

    with schema_context("public"):
        tenants = list(Tenant.objects.filter(is_active=True))
    total = 0
    for tenant in tenants:
        with tenant_context(tenant):
            threshold = date.today() + timedelta(days=getattr(settings, "SEPA_PRENOTIFICATION_DAYS", 14))
            for batch in SepaBatch.objects.filter(
                status__in=[SepaBatch.Status.XML_CREATED, SepaBatch.Status.DRAFT],
                collection_date__lte=threshold,
            ):
                total += send_prenotifications_for_batch(batch)
    return {"sent": total}


@shared_task
def submit_batch(schema_name: str, batch_id: int):
    from apps.banking.tasks import submit_sepa_batch

    return submit_sepa_batch(schema_name, batch_id)
