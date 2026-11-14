from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import TenantCreateForm
from .models import Domain, Tenant


class TenantLoginView(LoginView):
    template_name = "core/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        schema = getattr(connection, "schema_name", "public")
        current_tenant = getattr(self.request, "tenant", None)

        if schema == "public":
            if not user.is_platform_admin:
                form.add_error(None, "Mandantenbenutzer müssen sich über ihre Mandanten-Domain anmelden.")
                return self.form_invalid(form)
        else:
            if not user.is_platform_admin and current_tenant and user.tenant_id != current_tenant.id:
                form.add_error(None, "Dieses Konto gehört nicht zu diesem Mandanten.")
                return self.form_invalid(form)

        response = super().form_valid(form)
        if schema == "public" and user.tenant and user.is_platform_admin:
            pass
        return response

    def get_success_url(self):
        user = self.request.user
        schema = getattr(connection, "schema_name", "public")
        if schema == "public" and user.tenant_id:
            domain = user.tenant.primary_domain
            if domain:
                scheme = "https" if self.request.is_secure() else "http"
                return f"{scheme}://{domain.domain}/"
        next_url = self.get_redirect_url()
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        return reverse("core:platform_home") if schema == "public" else reverse("dashboard:home")


class TenantLogoutView(LogoutView):
    next_page = "/accounts/login/"


def healthz(request):
    status = {"status": "ok", "database": "ok", "cache": "ok"}
    code = 200
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001
        status["database"] = f"error: {exc}"
        status["status"] = "degraded"
        code = 503
    try:
        from django.core.cache import cache

        cache.set("openfin:healthz", "1", 10)
        if cache.get("openfin:healthz") != "1":
            raise RuntimeError("cache read failed")
    except Exception as exc:  # noqa: BLE001
        status["cache"] = f"error: {exc}"
        status["status"] = "degraded"
        code = 503
    return JsonResponse(status, status=code)


@login_required
def platform_home(request):
    schema = getattr(connection, "schema_name", "public")
    user = request.user
    if not user.is_platform_admin:
        if schema != "public":
            return redirect("dashboard:home")
        if user.tenant_id:
            domain = user.tenant.primary_domain
            if domain:
                scheme = "https" if request.is_secure() else "http"
                return redirect(f"{scheme}://{domain.domain}/")
        messages.error(request, "Kein Mandant zugeordnet. Bitte den Plattform-Administrator kontaktieren.")
        return redirect("login")

    tenants = Tenant.objects.prefetch_related("domains").all()
    form = TenantCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        tenant = form.save()
        messages.success(request, f"Mandant „{tenant.name}“ wurde angelegt.")
        return redirect("core:platform_home")

    return render(
        request,
        "core/platform.html",
        {
            "tenants": tenants,
            "form": form,
            "platform_version": "1.0.0",
        },
    )


@login_required
@require_POST
def tenant_switch(request):
    if not request.user.is_platform_admin:
        return JsonResponse({"detail": "Nicht erlaubt."}, status=403)
    tenant_id = request.POST.get("tenant_id")
    tenant = Tenant.objects.filter(pk=tenant_id, is_active=True).first()
    if not tenant:
        messages.error(request, "Mandant nicht gefunden.")
        return redirect("core:platform_home")
    domain = tenant.primary_domain
    if not domain:
        messages.error(request, "Für diesen Mandanten ist keine Domain hinterlegt.")
        return redirect("core:platform_home")
    scheme = "https" if request.is_secure() else "http"
    return redirect(f"{scheme}://{domain.domain}/")
