from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django_tenants.models import DomainMixin, TenantMixin


class Tenant(TenantMixin):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=63, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_on = models.DateTimeField(auto_now_add=True)
    paid_until = models.DateField(null=True, blank=True)
    on_trial = models.BooleanField(default=True)
    auto_create_schema = True
    auto_drop_schema = False

    class Meta:
        ordering = ["name"]
        verbose_name = "Mandant"
        verbose_name_plural = "Mandanten"

    def __str__(self) -> str:
        return self.name

    @property
    def primary_domain(self):
        return self.domains.filter(is_primary=True).first() or self.domains.first()

    def get_absolute_url(self) -> str:
        domain = self.primary_domain
        return f"http://{domain.domain}/" if domain else "/"


class Domain(DomainMixin):
    class Meta:
        verbose_name = "Domain"
        verbose_name_plural = "Domains"

    def __str__(self) -> str:
        return self.domain


class User(AbstractUser):
    tenant = models.ForeignKey(
        Tenant,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
        help_text="Leer = Plattform-Administrator (public schema).",
    )
    is_platform_admin = models.BooleanField(
        default=False,
        help_text="Darf Mandanten anlegen und zwischen Mandanten wechseln.",
    )

    class Meta:
        verbose_name = "Benutzer"
        verbose_name_plural = "Benutzer"

    @property
    def effective_tenant(self):
        return self.tenant

    def belongs_to(self, tenant) -> bool:  # noqa: ANN001
        return self.is_platform_admin or (tenant is not None and self.tenant_id == tenant.id)

    def get_absolute_url(self) -> str:
        return reverse("core:platform_home")
