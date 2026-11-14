from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import logout
from django.db import connection
from django.shortcuts import redirect
from django.urls import reverse

PUBLIC_ALLOWED_PREFIXES = (
    "/platform/",
    "/admin/",
    "/accounts/",
    "/healthz/",
    "/api/schema/",
    "/api/docs/",
    "/api/webhooks/",
    "/static/",
    "/media/",
    "/page/",
    "/cms/",
    "/favicon.ico",
)


class PublicSchemaMiddleware:
    """Trennt public-Schema (Plattform) strikt von Tenant-Schemata."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        schema = getattr(connection, "schema_name", "public")

        if schema == "public":
            if not any(request.path_info.startswith(prefix) for prefix in PUBLIC_ALLOWED_PREFIXES):
                if request.path_info != "/":
                    messages.info(request, "Bitte zuerst einen Mandanten auswählen.")
                return redirect(reverse("core:platform_home"))
        else:
            tenant = getattr(request, "tenant", None)
            user = getattr(request, "user", None)
            if user and user.is_authenticated and not user.is_platform_admin:
                if user.tenant_id and tenant and user.tenant_id != tenant.id:
                    logout(request)
                    messages.error(request, "Ihr Benutzerkonto gehört nicht zu diesem Mandanten.")
                    return redirect(reverse("login"))

        return self.get_response(request)
