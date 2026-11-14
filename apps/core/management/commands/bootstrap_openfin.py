from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context, tenant_context

from apps.core.models import Domain, Tenant


class Command(BaseCommand):
    help = "Legt Plattform-Admin, Demo-Mandant, Domains und Demo-Daten an."

    def add_arguments(self, parser):
        parser.add_argument("--admin-password", default=os.environ.get("OPENFIN_ADMIN_PASSWORD", "admin12345"))
        parser.add_argument("--tenant-password", default=os.environ.get("OPENFIN_TENANT_PASSWORD", "demo12345"))
        parser.add_argument("--skip-demo", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        with schema_context("public"):
            platform_admin, created = User.objects.get_or_create(
                username="admin",
                defaults={
                    "email": "admin@openfin.local",
                    "is_staff": True,
                    "is_superuser": True,
                    "is_platform_admin": True,
                },
            )
            platform_admin.is_staff = True
            platform_admin.is_superuser = True
            platform_admin.is_platform_admin = True
            platform_admin.set_password(options["admin_password"])
            platform_admin.save()

            tenant, tenant_created = Tenant.objects.get_or_create(
                schema_name="demo",
                defaults={
                    "name": "OpenFin Demo",
                    "slug": "demo",
                    "description": "Demo-Mandant mit Mock-FinTS, ERPNext und Payment-Providern.",
                    "on_trial": True,
                },
            )
            for domain_name, is_primary in [
                ("localhost", True),
                ("127.0.0.1", False),
                ("demo.localhost", False),
                ("demo.openfin.local", False),
            ]:
                Domain.objects.get_or_create(
                    domain=domain_name,
                    defaults={"tenant": tenant, "is_primary": is_primary},
                )

            demo_user, _ = User.objects.get_or_create(
                username="demo",
                defaults={
                    "email": "demo@openfin.local",
                    "tenant": tenant,
                    "is_staff": True,
                },
            )
            demo_user.tenant = tenant
            demo_user.is_staff = True
            demo_user.set_password(options["tenant_password"])
            demo_user.save()

        if not options["skip_demo"]:
            with tenant_context(tenant):
                call_command("seed_demo", verbosity=options.get("verbosity", 1))

        self.stdout.write(self.style.SUCCESS("\nOpenFin Bootstrap abgeschlossen."))
        self.stdout.write("Plattform:  http://localhost:8045/platform/")
        self.stdout.write("Mandant:    http://localhost:8045/")
        self.stdout.write(f"Admin:      admin / {options['admin_password']}")
        self.stdout.write(f"Mandant:    demo / {options['tenant_password']}")
        self.stdout.write("Hinweis:    Passwörter nach dem ersten Login ändern.")
