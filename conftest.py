from __future__ import annotations

import pytest
from django_tenants.utils import schema_context, tenant_context


@pytest.fixture
def tenant(db):
    from apps.core.models import Domain, Tenant

    with schema_context("public"):
        for existing in list(Tenant.objects.filter(schema_name="test")):
            existing.delete(force_drop=True)
        tenant = Tenant(schema_name="test", name="Test Tenant", slug="test")
        tenant.save()
        Domain.objects.create(domain="test.localhost", tenant=tenant, is_primary=True)
    yield tenant
    with schema_context("public"):
        Domain.objects.filter(tenant=tenant).delete()
        for existing in list(Tenant.objects.filter(pk=tenant.pk)):
            existing.delete(force_drop=True)


@pytest.fixture
def tenant_ctx(tenant):
    with tenant_context(tenant):
        yield tenant


@pytest.fixture
def user_in_tenant(tenant, django_user_model):
    from django_tenants.utils import schema_context

    with schema_context("public"):
        user = django_user_model.objects.create_user(
            username="tenantuser",
            password="testpass123",
            tenant=tenant,
            is_staff=True,
        )
    return user


@pytest.fixture
def logged_client(client, user_in_tenant):
    client.force_login(user_in_tenant)
    return client


@pytest.fixture
def tenant_client(client, user_in_tenant):
    client.force_login(user_in_tenant)
    client.defaults["HTTP_HOST"] = "test.localhost"
    return client
