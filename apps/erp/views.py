from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import ERPConfigForm
from .models import ERPConfig, ExpectedPayment, PurchaseInvoice, ReconciliationMatch
from .services import active_config, process_sales_invoice, sync_purchase_invoices, verify_webhook_signature


@login_required
def erp_dashboard(request):
    config = active_config()
    return render(
        request,
        "erp/dashboard.html",
        {
            "config": config,
            "configs": ERPConfig.objects.all(),
            "expected": ExpectedPayment.objects.filter(status=ExpectedPayment.Status.OPEN)[:20],
            "matches": ReconciliationMatch.objects.select_related("transaction", "expected_payment")[:20],
            "purchases": PurchaseInvoice.objects.all()[:20],
        },
    )


@login_required
def config_edit(request, pk=None):
    config = get_object_or_404(ERPConfig, pk=pk) if pk else ERPConfig()
    if config.pk is None and ERPConfig.objects.exists():
        config = ERPConfig.objects.first()
    form = ERPConfigForm(request.POST or None, instance=config)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "ERPNext-Konfiguration gespeichert.")
        return redirect("erp:dashboard")
    return render(request, "erp/config_form.html", {"form": form, "config": config})


@login_required
def expected_payment_list(request):
    qs = ExpectedPayment.objects.all()
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "erp/expected_list.html",
        {"payments": qs.select_related("erp_config"), "status": status},
    )


@login_required
@require_POST
def sync_purchases(request):
    result = sync_purchase_invoices()
    if result.get("status") == "ok":
        messages.success(request, f"{result['fetched']} Eingangsrechnungen abgerufen, {result['queued']} in den Ausgangskorb gelegt.")
    else:
        messages.warning(request, result.get("reason", "Sync nicht möglich."))
    return redirect("erp:dashboard")


@csrf_exempt
@require_POST
def sales_invoice_webhook(request):
    body = request.body
    secret_config = active_config()
    secret = (secret_config.webhook_secret if secret_config else "") or None
    signature = request.headers.get("X-Frappe-Webhook-Signature") or request.headers.get("X-OpenFin-Signature", "")
    if not verify_webhook_signature(body, signature, secret):
        return JsonResponse({"detail": "Ungültige Signatur."}, status=403)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": "Ungültiges JSON."}, status=400)
    payment = process_sales_invoice(payload, secret_config)
    return JsonResponse(
        {
            "status": "ok",
            "invoice_id": payment.invoice_id,
            "expected_payment_id": payment.pk,
            "amount": str(payment.amount),
        }
    )
