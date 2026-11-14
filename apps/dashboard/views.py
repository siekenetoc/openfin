from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.banking.forecasting import cashflow_forecast
from apps.banking.models import BankAccount, BankTransaction, TANChallenge
from apps.billing.models import SepaBatch
from apps.erp.models import ExpectedPayment, ReconciliationMatch
from apps.erp.reconciliation import approve_match, reject_match

from .csv_export import dataset_rows


@login_required
def home(request):
    accounts = BankAccount.objects.filter(is_active=True)
    total_balance = accounts.aggregate(total=Sum("balance"))["total"] or 0
    recent = BankTransaction.objects.select_related("account")[:12]
    triage = BankTransaction.objects.filter(status=BankTransaction.Status.NEEDS_REVIEW).count()
    pending_tans = TANChallenge.objects.filter(status=TANChallenge.Status.PENDING)[:5]
    open_expected = ExpectedPayment.objects.filter(status=ExpectedPayment.Status.OPEN)
    forecast = cashflow_forecast(30)
    return render(
        request,
        "dashboard/home.html",
        {
            "accounts": accounts[:6],
            "total_balance": total_balance,
            "recent_transactions": recent,
            "triage_count": triage,
            "pending_tans": pending_tans,
            "open_expected_count": open_expected.count(),
            "open_expected_total": open_expected.aggregate(total=Sum("amount"))["total"] or 0,
            "forecast": forecast,
            "forecast_60": cashflow_forecast(60),
            "forecast_90": cashflow_forecast(90),
            "sepa_batches": SepaBatch.objects.select_related("account")[:5],
        },
    )


@login_required
def triage(request):
    transactions = list(
        BankTransaction.objects.filter(status=BankTransaction.Status.NEEDS_REVIEW)
        .select_related("account")
        .prefetch_related("reconciliation_matches__expected_payment")
        .order_by("-booking_date")[:100]
    )
    for tx in transactions:
        matches = sorted(
            [match for match in tx.reconciliation_matches.all() if match.status == ReconciliationMatch.Status.PROPOSED],
            key=lambda match: match.score,
            reverse=True,
        )
        tx.proposed_match = matches[0] if matches else None
        tx.alternatives = matches[1:]
        tx.amount_diff = 0
        if tx.proposed_match:
            tx.amount_diff = tx.amount - tx.proposed_match.expected_payment.amount
    return render(request, "dashboard/triage.html", {"transactions": transactions})


@login_required
@require_POST
def triage_approve(request, match_id):
    match = get_object_or_404(ReconciliationMatch, pk=match_id, status=ReconciliationMatch.Status.PROPOSED)
    approve_match(match)
    response = HttpResponse("", content_type="text/html")
    response["HX-Trigger"] = "triageApproved"
    return response


@login_required
@require_POST
def triage_reject(request, match_id):
    match = get_object_or_404(ReconciliationMatch, pk=match_id)
    reject_match(match)
    tx = match.transaction
    matches = sorted(
        [m for m in tx.reconciliation_matches.all() if m.status == ReconciliationMatch.Status.PROPOSED],
        key=lambda m: m.score,
        reverse=True,
    )
    tx.proposed_match = matches[0] if matches else None
    tx.alternatives = matches[1:]
    tx.amount_diff = tx.amount - tx.proposed_match.expected_payment.amount if tx.proposed_match else 0
    return render(request, "dashboard/partials/triage_row.html", {"tx": tx})


@login_required
def triage_alternatives(request, tx_id):
    tx = get_object_or_404(BankTransaction, pk=tx_id)
    matches = tx.reconciliation_matches.exclude(status=ReconciliationMatch.Status.REJECTED).select_related("expected_payment")
    return render(
        request,
        "dashboard/partials/triage_alternatives.html",
        {"tx": tx, "matches": matches},
    )


@login_required
def export(request, dataset: str):
    filters = {
        "ids": request.GET.get("ids", ""),
        "date_from": request.GET.get("date_from") or None,
        "date_to": request.GET.get("date_to") or None,
        "status": request.GET.get("status", ""),
        "q": request.GET.get("q", ""),
    }
    try:
        rows = dataset_rows(dataset, filters)
    except ValueError:
        return HttpResponse("Unbekannter Export.", status=404)
    response = StreamingHttpResponse(rows, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="openfin-{dataset}.csv"'
    return response
