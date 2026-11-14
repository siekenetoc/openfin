from __future__ import annotations

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.banking.models import BankTransaction

from .ai import LocalAIError, LocalAIClient, categorize_uncategorized
from .datev import build_extf_csv
from .forms import AIQueryForm, DATEVConfigForm
from .models import AICategorization, AIQuery, DATEVConfig, PaperlessDocumentLink
from .paperless import PaperlessClient, PaperlessError


@login_required
def integrations_dashboard(request):
    client = LocalAIClient()
    return render(
        request,
        "integrations/dashboard.html",
        {
            "datev_configs": DATEVConfig.objects.all(),
            "paperless_links": PaperlessDocumentLink.objects.select_related("transaction")[:15],
            "ai_results": AICategorization.objects.select_related("transaction")[:15],
            "queries": AIQuery.objects.all()[:10],
            "ai_configured": client.configured,
            "ai_model": client.model,
            "paperless_configured": PaperlessClient().configured,
        },
    )


@login_required
def datev_config(request):
    config = DATEVConfig.objects.first() or DATEVConfig()
    form = DATEVConfigForm(request.POST or None, instance=config)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "DATEV-Konfiguration gespeichert.")
        return redirect("integrations:dashboard")
    return render(request, "integrations/datev_config.html", {"form": form, "config": config})


@login_required
def datev_export(request):
    config = DATEVConfig.objects.filter(is_active=True).first()
    if not config:
        messages.error(request, "Bitte zuerst eine DATEV-Konfiguration anlegen.")
        return redirect("integrations:datev_config")
    today = date.today()
    try:
        date_from = date.fromisoformat(request.GET.get("date_from", "")) if request.GET.get("date_from") else today.replace(day=1)
        date_to = date.fromisoformat(request.GET.get("date_to", "")) if request.GET.get("date_to") else today
    except ValueError:
        messages.error(request, "Ungültiger Zeitraum.")
        return redirect("integrations:dashboard")
    content = build_extf_csv(config, date_from, date_to)
    response = HttpResponse(content, content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = (
        f'attachment; filename="DATEV-EXTF-{date_from.isoformat()}-{date_to.isoformat()}.csv"'
    )
    return response


@login_required
@require_POST
def paperless_autolink_all(request):
    try:
        linked = PaperlessClient().autolink()
        messages.success(request, f"{linked} Belege verknüpft.")
    except PaperlessError as exc:
        messages.error(request, str(exc))
    return redirect("integrations:dashboard")


@login_required
@require_POST
def paperless_link_transaction(request, pk):
    tx = get_object_or_404(BankTransaction, pk=pk)
    try:
        client = PaperlessClient()
        document, score = client.find_for_transaction(tx)
        if document:
            client.link_transaction(tx, document, score)
            messages.success(request, f"Beleg „{document.get('title', document.get('id'))}“ verknüpft ({score} %).")
        else:
            messages.warning(request, "Kein passender Beleg gefunden.")
    except PaperlessError as exc:
        messages.error(request, str(exc))
    return redirect(request.META.get("HTTP_REFERER", "/banking/transactions/"))


@login_required
@require_POST
def ai_categorize_transaction(request, pk):
    tx = get_object_or_404(BankTransaction, pk=pk)
    client = LocalAIClient()
    categorization = client.categorize(tx)
    tx.category = categorization.category
    tx.cost_center = categorization.cost_center
    tx.save(update_fields=["category", "cost_center"])
    categorization.accepted = True
    categorization.save(update_fields=["accepted"])
    messages.success(request, f"Kategorie: {categorization.category} ({categorization.confidence} %).")
    return redirect(request.META.get("HTTP_REFERER", "/banking/transactions/"))


@login_required
@require_POST
def ai_categorize_batch(request):
    count = categorize_uncategorized()
    messages.success(request, f"{count} Umsätze kategorisiert.")
    return redirect("integrations:dashboard")


@login_required
def ai_query(request):
    form = AIQueryForm(request.POST or None)
    result = None
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            result = LocalAIClient().text_to_sql(form.cleaned_data["question"])
        except LocalAIError as exc:
            error = str(exc)
    return render(
        request,
        "integrations/ai_query.html",
        {"form": form, "result": result, "error": error},
    )
