from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class ContentPage(models.Model):
    tenant = models.ForeignKey(
        "core.Tenant",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="content_pages",
        help_text="Leer = global für alle Mandanten.",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    content_html = models.TextField(blank=True)
    header_image = models.ImageField(upload_to="cms/", blank=True, null=True)
    meta_description = models.CharField(max_length=320, blank=True)
    is_published = models.BooleanField(default=True)
    show_in_footer = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="cms_page_tenant_slug"),
        ]
        verbose_name = "CMS-Seite"
        verbose_name_plural = "CMS-Seiten"

    def __str__(self) -> str:
        scope = self.tenant.name if self.tenant_id else "global"
        return f"{self.title} ({scope})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("cms:page_detail", kwargs={"slug": self.slug})
