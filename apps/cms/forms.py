from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from .models import ContentPage

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml"}


class ContentPageForm(forms.ModelForm):
    class Meta:
        model = ContentPage
        fields = [
            "title",
            "slug",
            "content_html",
            "header_image",
            "meta_description",
            "is_published",
            "show_in_footer",
        ]
        widgets = {
            "content_html": forms.HiddenInput(),
            "meta_description": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_slug(self):
        slug = self.cleaned_data["slug"]
        tenant = getattr(self.instance, "tenant", None)
        qs = ContentPage.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if tenant is None:
            qs = qs.filter(tenant__isnull=True)
        else:
            qs = qs.filter(tenant=tenant)
        if qs.exists():
            raise ValidationError("Für diesen Mandanten existiert bereits eine Seite mit diesem Slug.")
        return slug


class CmsImageUploadForm(forms.Form):
    image = forms.ImageField()

    def clean_image(self):
        image = self.cleaned_data["image"]
        if image.size > MAX_IMAGE_BYTES:
            raise ValidationError("Bild ist größer als 10 MB.")
        content_type = getattr(image, "content_type", "")
        if content_type and content_type not in ALLOWED_IMAGE_TYPES:
            raise ValidationError("Nicht unterstützter Bildtyp.")
        return image
