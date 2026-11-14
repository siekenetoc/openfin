from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Domain, Tenant


class Command(BaseCommand):
    help = "Legt einen Mandanten inklusive primärer Domain und Admin-Benutzer an."

    def add_arguments(self, parser):
        parser.add_argument("schema_name")
        parser.add_argument("name")
        parser.add_argument("domain")
        parser.add_argument("--admin-username", default="admin")
        parser.add_argument("--admin-email", default="")
        parser.add_argument("--admin-password", default="change-me-now")

    @transaction.atomic
    def handle(self, *args, **options):
        schema = options["schema_name"]
        if Tenant.objects.filter(schema_name=schema).exists():
            raise CommandError(f"Schema {schema} existiert bereits.")
        tenant = Tenant.objects.create(
            schema_name=schema,
            name=options["name"],
            slug=schema,
            on_trial=True,
        )
        Domain.objects.create(domain=options["domain"].lower(), tenant=tenant, is_primary=True)
        User = get_user_model()
        User.objects.create_user(
            username=options["admin_username"],
            email=options["admin_email"],
            password=options["admin_password"],
            tenant=tenant,
            is_staff=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Mandant {tenant.name} ({tenant.schema_name}) angelegt."))
        self.stdout.write(f"Domain: https://{options['domain']}/")
