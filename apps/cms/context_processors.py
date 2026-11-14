from __future__ import annotations

from django.db import connection
from django.db.models import Q

from .models import ContentPage


def footer_pages(request):
    tenant = getattr(request, "tenant", None)
    if getattr(connection, "schema_name", "public") == "public":
        qs = ContentPage.objects.filter(is_published=True, show_in_footer=True, tenant__isnull=True)
    elif tenant is not None:
        qs = ContentPage.objects.filter(
            Q(tenant=tenant) | Q(tenant__isnull=True),
            is_published=True,
            show_in_footer=True,
        )
    else:
        qs = ContentPage.objects.none()

    pages = {}
    for page in qs.order_by("slug", "tenant_id"):
        pages[page.slug] = page
    return {"footer_pages": list(pages.values())}
