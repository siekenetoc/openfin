from __future__ import annotations

import logging

from celery import shared_task
from django_tenants.utils import schema_context, tenant_context

from apps.core.models import Tenant

logger = logging.getLogger("openfin.tasks.integrations")


@shared_task
def autolink_paperless_documents():
    from apps.integrations.paperless import PaperlessClient, PaperlessError

    client = PaperlessClient()
    if not client.configured:
        return {"status": "skipped", "reason": "Paperless nicht konfiguriert."}
    with schema_context("public"):
        tenants = list(Tenant.objects.filter(is_active=True))
    linked = 0
    for tenant in tenants:
        with tenant_context(tenant):
            try:
                linked += client.autolink()
            except PaperlessError:
                break
            except Exception:  # noqa: BLE001
                logger.exception("Paperless-Autolink für %s fehlgeschlagen", tenant.schema_name)
    return {"linked": linked}


@shared_task
def categorize_transactions():
    from apps.integrations.ai import categorize_uncategorized

    with schema_context("public"):
        tenants = list(Tenant.objects.filter(is_active=True))
    total = 0
    for tenant in tenants:
        with tenant_context(tenant):
            try:
                total += categorize_uncategorized()
            except Exception:  # noqa: BLE001
                logger.exception("KI-Kategorisierung für %s fehlgeschlagen", tenant.schema_name)
    return {"categorized": total}
