from __future__ import annotations

from django.db import connection


def navigation(request):
    tenant = getattr(request, "tenant", None)
    user = getattr(request, "user", None)
    context = {
        "current_tenant": tenant,
        "is_platform_admin": bool(getattr(user, "is_platform_admin", False)),
        "pending_tan_count": 0,
        "triage_count": 0,
        "open_payment_count": 0,
        "platform_tenants": [],
    }
    if getattr(user, "is_platform_admin", False):
        from apps.core.models import Tenant

        context["platform_tenants"] = list(Tenant.objects.filter(is_active=True).order_by("name"))
    if getattr(connection, "schema_name", "public") == "public" or tenant is None:
        return context

    try:
        from apps.banking.models import BankTransaction, TANChallenge
        from apps.erp.models import ExpectedPayment

        context["pending_tan_count"] = TANChallenge.objects.filter(status=TANChallenge.Status.PENDING).count()
        context["triage_count"] = BankTransaction.objects.filter(
            status=BankTransaction.Status.NEEDS_REVIEW
        ).count()
        context["open_payment_count"] = ExpectedPayment.objects.filter(
            status=ExpectedPayment.Status.OPEN
        ).count()
    except Exception:  # noqa: BLE001 - Kontext darf nie die Seite brechen
        pass
    return context
