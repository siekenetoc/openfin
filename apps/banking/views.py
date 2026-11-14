from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.banking.forecasting import cashflow_forecast
from apps.banking.models import (
    BankAccount,
    BankTransaction,
    OutgoingPayment,
    StandingOrder,
    TANChallenge,
)
from apps.banking.services.fints_client import TANRequired, get_fints_client
from apps.banking.services.sync import sync_account
from apps.banking.services.tan import confirm_tan_challenge, expire_challenge
from apps.banking.tasks import submit_outgoing_payment
from apps.billing.sepa import build_pain001

from .forms import BankAccountForm, OutgoingPaymentForm, StandingOrderForm, TransactionFilterForm


@login_required
def account_list(request):
    accounts = BankAccount.objects.all()
    total = accounts.aggregate(total=Sum("balance"))["total"] or 0
    return render(
        request,
        "banking/account_list.html",
        {
            "accounts": accounts,
            "total_balance": total,
            "forecast_30": cashflow_forecast(30),
            "forecast_60": cashflow_forecast(60),
            "forecast_90": cashflow_forecast(90),
            "pending_tans": TANChallenge.objects.filter(status=TANChallenge.Status.PENDING)[:5],
        },
    )


@login_required
def account_create(request):
    form = BankAccountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        account = form.save()
        messages.success(request, f"Konto „{account.name}“ angelegt.")
        return redirect("banking:account_detail", pk=account.pk)
    return render(request, "banking/account_form.html", {"form": form, "title": "Konto anlegen"})


@login_required
def account_edit(request, pk):
    account = get_object_or_404(BankAccount, pk=pk)
    form = BankAccountForm(request.POST or None, instance=account)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Konto aktualisiert.")
        return redirect("banking:account_detail", pk=account.pk)
    return render(request, "banking/account_form.html", {"form": form, "title": "Konto bearbeiten", "account": account})


@login_required
def account_detail(request, pk):
    account = get_object_or_404(BankAccount, pk=pk)
    transactions = account.transactions.all()[:50]
    return render(
        request,
        "banking/account_detail.html",
        {
            "account": account,
            "transactions": transactions,
            "pending_tans": account.tan_challenges.filter(status=TANChallenge.Status.PENDING),
            "payments": account.outgoing_payments.all()[:10],
            "standing_orders": account.standing_orders.all()[:10],
        },
    )


@login_required
@require_POST
def account_sync(request, pk):
    account = get_object_or_404(BankAccount, pk=pk)
    result = sync_account(account)
    response = render(
        request,
        "banking/partials/sync_result.html",
        {"account": account, "result": result},
    )
    if result.get("status") == "ok":
        response["HX-Trigger"] = "bankSynced"
    if result.get("status") == "pending_tan":
        response["HX-Trigger"] = json.dumps(
            {"tanRequired": {"url": reverse("banking:tan_modal", args=[result["challenge_id"]])}}
        )
    return response


@login_required
def transaction_list(request):
    form = TransactionFilterForm(request.GET or None)
    qs = BankTransaction.objects.select_related("account")
    if form.is_valid():
        data = form.cleaned_data
        if data.get("account"):
            qs = qs.filter(account=data["account"])
        if data.get("status"):
            qs = qs.filter(status=data["status"])
        if data.get("date_from"):
            qs = qs.filter(booking_date__gte=data["date_from"])
        if data.get("date_to"):
            qs = qs.filter(booking_date__lte=data["date_to"])
        if data.get("search"):
            term = data["search"]
            qs = qs.filter(
                Q(counterparty_name__icontains=term)
                | Q(purpose__icontains=term)
                | Q(counterparty_iban__icontains=term)
            )
    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "banking/transaction_list.html", {"form": form, "page_obj": page})


@login_required
def payment_list(request):
    payments = OutgoingPayment.objects.select_related("account").all()
    return render(
        request,
        "banking/payment_list.html",
        {"payments": payments, "pending_tans": TANChallenge.objects.filter(status=TANChallenge.Status.PENDING)},
    )


@login_required
def payment_create(request):
    form = OutgoingPaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        payment = form.save()
        payment.pain_xml = build_pain001(payment, tenant=getattr(request, "tenant", None))
        payment.save(update_fields=["pain_xml"])
        messages.success(request, "Zahlung im Ausgangskorb angelegt.")
        return redirect("banking:payment_detail", pk=payment.pk)
    return render(request, "banking/payment_form.html", {"form": form, "title": "Zahlung anlegen"})


@login_required
def payment_detail(request, pk):
    payment = get_object_or_404(OutgoingPayment.objects.select_related("account"), pk=pk)
    return render(request, "banking/payment_detail.html", {"payment": payment})


@login_required
@require_POST
def payment_submit(request, pk):
    payment = get_object_or_404(OutgoingPayment, pk=pk)
    if payment.status not in {OutgoingPayment.Status.DRAFT, OutgoingPayment.Status.FAILED}:
        messages.warning(request, "Diese Zahlung kann nicht erneut eingereicht werden.")
        return redirect("banking:payment_detail", pk=pk)
    result = submit_outgoing_payment(connection.schema_name, payment.pk)
    payment.refresh_from_db()
    if result.get("status") == "pending_tan":
        messages.warning(request, "Die Bank verlangt eine TAN-Freigabe.")
    elif result.get("status") == "error":
        messages.error(request, result.get("message", "Unbekannter Fehler."))
    else:
        messages.success(request, "Zahlung wurde eingereicht.")
    return redirect("banking:payment_detail", pk=pk)


@login_required
@require_POST
def payment_cancel(request, pk):
    payment = get_object_or_404(OutgoingPayment, pk=pk)
    if payment.status in {OutgoingPayment.Status.DRAFT, OutgoingPayment.Status.PENDING_TAN, OutgoingPayment.Status.FAILED}:
        payment.status = OutgoingPayment.Status.CANCELLED
        payment.save(update_fields=["status"])
        messages.success(request, "Zahlung storniert.")
    return redirect("banking:payment_detail", pk=pk)


@login_required
def standing_order_list(request):
    orders = StandingOrder.objects.select_related("account").all()
    return render(request, "banking/standing_order_list.html", {"orders": orders})


@login_required
def standing_order_create(request):
    form = StandingOrderForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        order = form.save(commit=False)
        order.pending_action = StandingOrder.Action.CREATE
        order.save()
        messages.success(request, "Dauerauftrag angelegt und zur Einreichung markiert.")
        return redirect("banking:standing_order_list")
    return render(request, "banking/standing_order_form.html", {"form": form})


@login_required
@require_POST
def standing_order_delete(request, pk):
    order = get_object_or_404(StandingOrder, pk=pk)
    order.pending_action = StandingOrder.Action.DELETE
    order.is_active = False
    order.save(update_fields=["pending_action", "is_active"])
    messages.info(request, "Dauerauftrag zur Löschung markiert.")
    return redirect("banking:standing_order_list")


@login_required
def tan_modal(request, pk):
    challenge = get_object_or_404(TANChallenge, pk=pk)
    return render(request, "banking/partials/tan_modal.html", {"challenge": challenge})


@login_required
@require_POST
def tan_confirm(request, pk):
    challenge = get_object_or_404(TANChallenge, pk=pk)
    response = request.POST.get("tan", "").strip()
    if challenge.is_expired:
        expire_challenge(challenge)
    elif not response:
        return render(
            request,
            "banking/partials/tan_modal.html",
            {"challenge": challenge, "error": "Bitte TAN eingeben."},
            status=400,
        )
    else:
        challenge = confirm_tan_challenge(challenge, response)
    if challenge.status == TANChallenge.Status.CONFIRMED:
        response = render(request, "banking/partials/tan_result.html", {"challenge": challenge})
        response["HX-Trigger"] = "tanConfirmed"
        return response
    return render(
        request,
        "banking/partials/tan_modal.html",
        {"challenge": challenge, "error": challenge.error_message or "TAN-Freigabe fehlgeschlagen."},
        status=400,
    )


@login_required
@require_POST
def tan_cancel(request, pk):
    challenge = get_object_or_404(TANChallenge, pk=pk)
    challenge.status = TANChallenge.Status.CANCELLED
    challenge.save(update_fields=["status"])
    challenge.account.needs_tan = False
    challenge.account.save(update_fields=["needs_tan"])
    return render(request, "banking/partials/tan_result.html", {"challenge": challenge})


@login_required
def transaction_export(request):
    """Kompakter CSV-Export (die universelle, gefilterte Variante liegt im Dashboard)."""
    import csv

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="transaktionen.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["Datum", "Konto", "Betrag", "Währung", "Gegenpartei", "IBAN", "Verwendungszweck", "Status"])
    for tx in BankTransaction.objects.select_related("account").all():
        writer.writerow(
            [
                tx.booking_date,
                tx.account.name,
                str(tx.amount).replace(".", ","),
                tx.currency,
                tx.counterparty_name,
                tx.counterparty_iban,
                tx.purpose,
                tx.get_status_display(),
            ]
        )
    return response
