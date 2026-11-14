from __future__ import annotations

import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import connection
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .forms import CmsImageUploadForm, ContentPageForm
from .models import ContentPage


def _visible_pages(request):
    tenant = getattr(request, "tenant", None)
    if getattr(connection, "schema_name", "public") == "public":
        return ContentPage.objects.filter(tenant__isnull=True)
    if tenant is None:
        return ContentPage.objects.none()
    return ContentPage.objects.filter(Q(tenant=tenant) | Q(tenant__isnull=True))


def page_detail(request, slug):
    pages = [page for page in _visible_pages(request).filter(slug=slug, is_published=True)]
    if not pages:
        # Fallback auf globale Seite, falls eine mandantenspezifische fehlt.
        pages = list(ContentPage.objects.filter(slug=slug, is_published=True, tenant__isnull=True))
    if not pages:
        return render(request, "cms/page_missing.html", {"slug": slug}, status=404)
    pages.sort(key=lambda page: (page.tenant_id is None, page.title))
    page = pages[0]
    return render(request, "cms/page_detail.html", {"page": page})


@login_required
def editor_list(request):
    if not (request.user.is_staff or request.user.is_platform_admin):
        return JsonResponse({"detail": "Nicht erlaubt."}, status=403)
    tenant = getattr(request, "tenant", None)
    qs = ContentPage.objects.all()
    if tenant is not None:
        qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))
    else:
        qs = qs.filter(tenant__isnull=True)
    return render(request, "cms/editor_list.html", {"pages": qs.order_by("slug")})


@login_required
def editor_edit(request, pk=None):
    if not (request.user.is_staff or request.user.is_platform_admin):
        return JsonResponse({"detail": "Nicht erlaubt."}, status=403)
    tenant = getattr(request, "tenant", None)
    page = get_object_or_404(ContentPage, pk=pk) if pk else ContentPage()
    if pk and tenant is not None and page.tenant_id not in (tenant.id, None):
        return JsonResponse({"detail": "Nicht erlaubt."}, status=403)

    form = ContentPageForm(request.POST or None, request.FILES or None, instance=page)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if tenant is not None and obj.tenant_id is None:
            obj.tenant = tenant
        elif tenant is None and not request.user.is_platform_admin:
            messages.error(request, "Globale Seiten dürfen nur Plattform-Administratoren bearbeiten.")
            return redirect("cms:editor_list")
        obj.save()
        messages.success(request, "Seite gespeichert.")
        return redirect("cms:editor_edit", pk=obj.pk)

    return render(
        request,
        "cms/editor.html",
        {
            "form": form,
            "page": page,
            "upload_url": "/cms/upload-image/",
        },
    )


@login_required
@require_POST
def upload_image(request):
    if not (request.user.is_staff or request.user.is_platform_admin):
        return JsonResponse({"detail": "Nicht erlaubt."}, status=403)
    form = CmsImageUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"detail": form.errors.as_json()}, status=400)
    image = form.cleaned_data["image"]
    extension = image.name.rsplit(".", 1)[-1].lower() if "." in image.name else "bin"
    filename = f"cms/{uuid.uuid4().hex}.{slugify(extension) or 'bin'}"
    saved_name = default_storage.save(filename, image)
    url = default_storage.url(saved_name)
    return JsonResponse({"url": url, "name": saved_name})
