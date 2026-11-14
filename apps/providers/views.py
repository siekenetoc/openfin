from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.banking.forecasting import cashflow_forecast
from apps.banking.models import BankAccount
from apps.providers.depot import depot_summary, refresh_position_prices
from apps.providers.models import DepotPosition, ScrapeRun
from apps.providers.paypal import sync_paypal_account
from apps.providers.tasks import scrape_amazon


@login_required
def provider_dashboard(request):
    paypal_accounts = BankAccount.objects.filter(provider=BankAccount.Provider.PAYPAL)
    depot_accounts = BankAccount.objects.filter(account_type=BankAccount.AccountType.DEPOT)
    depots = [depot_summary(account) for account in depot_accounts]
    return render(
        request,
        "providers/dashboard.html",
        {
            "paypal_accounts": paypal_accounts,
            "depots": depots,
            "scrape_runs": ScrapeRun.objects.select_related("account")[:15],
            "forecast": cashflow_forecast(90),
            "playwright_available": True,
        },
    )


@login_required
@require_POST
def paypal_sync(request, pk):
    account = get_object_or_404(BankAccount, pk=pk, provider=BankAccount.Provider.PAYPAL)
    result = sync_paypal_account(account)
    if result.get("status") == "ok":
        messages.success(request, f"PayPal: {result['created']} neue Transaktionen.")
    else:
        messages.warning(request, result.get("reason", "PayPal-Sync nicht möglich."))
    return redirect("providers:dashboard")


@login_required
@require_POST
def depot_refresh(request, pk):
    account = get_object_or_404(BankAccount, pk=pk, account_type=BankAccount.AccountType.DEPOT)
    result = refresh_position_prices(account)
    messages.success(request, f"Kurse aktualisiert: {result.get('updated', 0)} Positionen.")
    return redirect("providers:dashboard")


@login_required
@require_POST
def amazon_scrape(request, pk):
    account = get_object_or_404(BankAccount, pk=pk)
    run = ScrapeRun.objects.create(account=account, scraper="amazon")
    tenant = getattr(request, "tenant", None)
    scrape_amazon.delay(tenant.schema_name if tenant else "public", account.pk, run.pk)
    messages.info(request, "Amazon-Scrape wurde gestartet. Ergebnisse erscheinen in der Lauf-Liste.")
    return redirect("providers:dashboard")


@login_required
def depot_detail(request, pk):
    account = get_object_or_404(BankAccount, pk=pk, account_type=BankAccount.AccountType.DEPOT)
    return render(request, "providers/depot_detail.html", {"summary": depot_summary(account)})


@login_required
def position_create(request, pk):
    account = get_object_or_404(BankAccount, pk=pk, account_type=BankAccount.AccountType.DEPOT)
    if request.method == "POST":
        DepotPosition.objects.create(
            account=account,
            isin=request.POST.get("isin", "").upper(),
            name=request.POST.get("name", ""),
            quantity=request.POST.get("quantity") or 0,
            price=request.POST.get("price") or 0,
            yahoo_symbol=request.POST.get("yahoo_symbol", ""),
        )
        messages.success(request, "Position angelegt.")
        return redirect("providers:depot_detail", pk=account.pk)
    return render(request, "providers/position_form.html", {"account": account})
