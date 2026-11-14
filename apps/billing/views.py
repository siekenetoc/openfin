from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.banking.models import BankAccount
from apps.erp.models import ExpectedPayment
from apps.erp.services import active_config

from .forms import SEPAMandateForm, SepaBatchCreateForm
from .models import PaymentLink, PaymentProviderConfig, SEPAMandate, SepaBatch, SepaBatchItem
from .services import (
    create_payment_link,
    create_sepa_batch,
    process_payment_event,
    provider_secret,
    send_prenotifications_for_batch,
    verify_hmac_signature,
    verify_stripe_signature,
)

logger = logging.getLogger("openfin.billing.views")


def _normalize_iban(iban: str) -> str:
    return (iban or "").replace(" ", "").upper()


def _match_mandate(payment: ExpectedPayment, mandates: list[SEPAMandate]) -> SEPAMandate | None:
    iban = _normalize_iban(payment.customer_iban)
    if iban:
        for mandate in mandates:
            if _normalize_iban(mandate.debtor_iban) == iban:
                return mandate
    try:
        from rapidfuzz import fuzz

        for mandate in mandates:
            if fuzz.token_set_ratio(mandate.debtor_name.lower(), payment.customer_name.lower()) >= 85:
                return mandate
    except Exception:  # noqa: BLE001
        pass
    return None


@login_required
def collection_dashboard(request):
    payments = list(
        ExpectedPayment.objects.filter(status=ExpectedPayment.Status.OPEN)
        .prefetch_related(Prefetch("payment_links", queryset=PaymentLink.objects.order_by("-created_at")))
        .order_by("due_date")
    )
    mandates = list(SEPAMandate.objects.filter(is_active=True))
    for payment in payments:
        payment.sepa_mandate = _match_mandate(payment, mandates)
        links = list(payment.payment_links.all())
        payment.latest_link = links[0] if links else None
    grouped = {
        "sepa": [p for p in payments if p.sepa_mandate],
        "stripe": [p for p in payments if p.latest_link and p.latest_link.provider == "stripe"],
        "paypal": [p for p in payments if p.latest_link and p.latest_link.provider == "paypal"],
        "wero": [p for p in payments if p.latest_link and p.latest_link.provider == "wero"],
        "other": [p for p in payments if not p.sepa_mandate and not p.latest_link],
    }
    return render(
        request,
        "billing/collection_dashboard.html",
        {
            "grouped": grouped,
            "payments": payments,
            "batches": SepaBatch.objects.select_related("account")[:10],
            "batch_form": SepaBatchCreateForm(),
            "due_soon": [p for p in payments if p.due_date <= date.today() + timedelta(days=14)],
            "payment_link_count": len([p for p in payments if p.latest_link]),
        },
    )


@login_required
def mandate_list(request):
    return render(request, "billing/mandate_list.html", {"mandates": SEPAMandate.objects.all()})


@login_required
def mandate_create(request):
    form = SEPAMandateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "SEPA-Mandat angelegt.")
        return redirect("billing:mandate_list")
    return render(request, "billing/mandate_form.html", {"form": form, "title": "SEPA-Mandat anlegen"})


@login_required
def mandate_edit(request, pk):
    mandate = get_object_or_404(SEPAMandate, pk=pk)
    form = SEPAMandateForm(request.POST or None, instance=mandate)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "SEPA-Mandat aktualisiert.")
        return redirect("billing:mandate_list")
    return render(request, "billing/mandate_form.html", {"form": form, "title": "SEPA-Mandat bearbeiten"})


@login_required
@require_POST
def sepa_batch_new(request):
    form = SepaBatchCreateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Bitte Konto und Einzugsdatum angeben.")
        return redirect("billing:collection_dashboard")
    payment_ids = request.POST.getlist("payment_ids")
    payments = list(ExpectedPayment.objects.filter(pk__in=payment_ids, status=ExpectedPayment.Status.OPEN))
    mandates = list(SEPAMandate.objects.filter(is_active=True))
    rows = []
    skipped = 0
    for payment in payments:
        mandate = _match_mandate(payment, mandates)
        if not mandate:
            skipped += 1
            continue
        rows.append(
            {
                "mandate": mandate,
                "expected_payment": payment,
                "amount": payment.amount,
                "purpose": f"Rechnung {payment.invoice_id}",
            }
        )
    if not rows:
        messages.error(request, "Keine ausgewählten Rechnungen haben ein aktives SEPA-Mandat.")
        return redirect("billing:collection_dashboard")
    batch = create_sepa_batch(
        account=form.cleaned_data["account"],
        collection_date=form.cleaned_data["collection_date"],
        rows=rows,
        description=form.cleaned_data["description"],
    )
    messages.success(request, f"SEPA-Batch {batch.batch_id} mit {len(rows)} Einzügen erzeugt. {skipped} ohne Mandat übersprungen.")
    return redirect("billing:sepa_batch_detail", pk=batch.pk)


@login_required
def sepa_batch_detail(request, pk):
    batch = get_object_or_404(SepaBatch.objects.select_related("account"), pk=pk)
    return render(request, "billing/sepa_batch_detail.html", {"batch": batch, "items": batch.items.all()})


@login_required
def sepa_batch_download(request, pk):
    batch = get_object_or_404(SepaBatch, pk=pk)
    response = HttpResponse(batch.xml_file or "", content_type="application/xml; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{batch.batch_id}.xml"'
    return response


@login_required
@require_POST
def sepa_batch_submit(request, pk):
    from apps.banking.tasks import submit_sepa_batch

    batch = get_object_or_404(SepaBatch, pk=pk)
    result = submit_sepa_batch(getattr(request, "tenant").schema_name if getattr(request, "tenant", None) else "public", batch.pk)
    if result.get("status") in {"submitted", "ok"}:
        messages.success(request, "SEPA-Batch wurde an die Bank übergeben.")
    else:
        messages.warning(request, f"Einreichung: {result}")
    return redirect("billing:sepa_batch_detail", pk=batch.pk)


@login_required
@require_POST
def sepa_batch_prenotify(request, pk):
    batch = get_object_or_404(SepaBatch, pk=pk)
    sent = send_prenotifications_for_batch(batch)
    messages.success(request, f"{sent} Vorabankündigungen versendet.")
    return redirect("billing:sepa_batch_detail", pk=pk)


@login_required
def payment_link_list(request):
    return render(
        request,
        "billing/payment_link_list.html",
        {"links": PaymentLink.objects.select_related("expected_payment").all()},
    )


@login_required
@require_POST
def payment_link_create(request):
    payment = get_object_or_404(ExpectedPayment, pk=request.POST.get("payment_id"))
    provider = request.POST.get("provider", "stripe")
    if provider not in dict(PaymentLink.Provider.choices):
        messages.error(request, "Unbekannter Provider.")
        return redirect("billing:collection_dashboard")
    try:
        link = create_payment_link(payment, provider, base_url=request.build_absolute_uri("/")[:-1])
        messages.success(request, f"Payment-Link ({provider}) erzeugt.")
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Payment-Link konnte nicht erzeugt werden: {exc}")
    return redirect("billing:collection_dashboard")


@login_required
def provider_config(request):
    from .forms import PaymentProviderConfigForm

    configs = PaymentProviderConfig.objects.all()
    config = configs.first() or PaymentProviderConfig()
    form = PaymentProviderConfigForm(request.POST or None, instance=config)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Provider-Konfiguration gespeichert.")
        return redirect("billing:provider_config")
    return render(request, "billing/provider_config.html", {"form": form, "configs": configs})


@csrf_exempt
@require_POST
def payment_webhook(request, provider: str):
    if provider not in dict(PaymentLink.Provider.choices):
        return JsonResponse({"detail": "Unbekannter Provider."}, status=404)
    body = request.body
    config = PaymentProviderConfig.objects.filter(provider=provider, is_active=True).first()
    secret = provider_secret(provider, config)

    if provider == "stripe":
        signature_valid = verify_stripe_signature(body, request.headers.get("Stripe-Signature", ""), secret)
    else:
        signature_valid = verify_hmac_signature(
            body,
            request.headers.get("X-Webhook-Signature", ""),
            secret,
        )
    if not signature_valid:
        return JsonResponse({"detail": "Ungültige Signatur."}, status=403)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": "Ungültiges JSON."}, status=400)

    event = process_payment_event(provider, payload, signature_valid=True, config=config)
    return JsonResponse(
        {
            "status": "ok",
            "event_id": event.event_id,
            "processed": event.processed,
            "invoice": event.expected_payment.invoice_id if event.expected_payment else None,
            "note": event.processing_error,
        }
    )


def payment_success(request):
    return render(request, "billing/payment_result.html", {"success": True})


def payment_cancelled(request):
    return render(request, "billing/payment_result.html", {"success": False})
