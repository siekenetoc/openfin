from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import Domain, Tenant, User


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 1


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "schema_name", "primary_domain_link", "is_active", "on_trial", "created_on")
    search_fields = ("name", "schema_name", "domains__domain")
    inlines = [DomainInline]
    readonly_fields = ("created_on",)

    @admin.display(description="Primäre Domain")
    def primary_domain_link(self, obj):
        domain = obj.primary_domain
        if not domain:
            return "—"
        return format_html('<a href="http://{0}/" target="_blank">{0}</a>', domain.domain)


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_primary")
    list_filter = ("is_primary", "tenant")
    search_fields = ("domain",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Mandant & Plattform", {"fields": ("tenant", "is_platform_admin")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Mandant & Plattform", {"fields": ("tenant", "is_platform_admin")}),
    )
    list_display = ("username", "email", "tenant", "is_platform_admin", "is_staff", "is_active")
    list_filter = ("is_platform_admin", "is_staff", "is_superuser", "tenant")
