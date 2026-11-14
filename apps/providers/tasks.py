from __future__ import annotations

import logging
from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone
from django_tenants.utils import schema_context, tenant_context

from apps.core.models import Tenant

logger = logging.getLogger("openfin.tasks.providers")


@shared_task
def sync_paypal(schema_name: str, account_id: int):
    from apps.banking.models import BankAccount
    from apps.providers.paypal import sync_paypal_account

    with schema_context("public"):
        tenant = Tenant.objects.get(schema_name=schema_name)
    with tenant_context(tenant):
        account = BankAccount.objects.get(pk=account_id)
        return sync_paypal_account(account)


@shared_task
def refresh_depot_prices(schema_name: str, account_id: int):
    from apps.banking.models import BankAccount
    from apps.providers.depot import refresh_position_prices

    with schema_context("public"):
        tenant = Tenant.objects.get(schema_name=schema_name)
    with tenant_context(tenant):
        account = BankAccount.objects.get(pk=account_id)
        return refresh_position_prices(account)


@shared_task
def refresh_all_depots():
    from apps.banking.models import BankAccount

    with schema_context("public"):
        tenants = list(Tenant.objects.filter(is_active=True))
    dispatched = 0
    for tenant in tenants:
        with tenant_context(tenant):
            for account in BankAccount.objects.filter(account_type=BankAccount.AccountType.DEPOT, is_active=True):
                refresh_depot_prices.delay(tenant.schema_name, account.pk)
                dispatched += 1
    return {"dispatched": dispatched}


@shared_task
def scrape_amazon(schema_name: str, account_id: int, run_id: int | None = None):
    from apps.banking.models import BankAccount
    from apps.providers.models import ScrapeRun
    from apps.providers.scrapers import AmazonScraper

    with schema_context("public"):
        tenant = Tenant.objects.get(schema_name=schema_name)
    with tenant_context(tenant):
        account = BankAccount.objects.get(pk=account_id)
        run = ScrapeRun.objects.get(pk=run_id) if run_id else ScrapeRun.objects.create(account=account, scraper="amazon")
        run.status = ScrapeRun.Status.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=["status", "started_at"])
        try:
            orders = AmazonScraper(account).scrape()
            run.items_found = len(orders)
            run.documents_saved = sum(1 for order in orders if order.invoice_path)
            run.status = ScrapeRun.Status.SUCCESS
        except Exception as exc:  # noqa: BLE001
            run.status = ScrapeRun.Status.FAILED
            run.error = str(exc)
            logger.exception("Amazon-Scrape fehlgeschlagen")
        run.finished_at = timezone.now()
        run.save()
        return {"status": run.status, "items": run.items_found, "documents": run.documents_saved}
