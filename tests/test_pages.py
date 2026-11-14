import pytest

from apps.banking.models import BankAccount

PAGES = [
    "/",
    "/banking/",
    "/banking/transactions/",
    "/triage/",
    "/billing/collections/",
    "/billing/mandates/",
    "/billing/payment-links/",
    "/erp/",
    "/erp/expected/",
    "/providers/",
    "/integrations/",
    "/integrations/ai/query/",
    "/cms/",
    "/page/agb/",
]


@pytest.mark.django_db
@pytest.mark.integration
@pytest.mark.parametrize("path", PAGES)
def test_pages_return_200(tenant_ctx, tenant_client, path):
    response = tenant_client.get(path, HTTP_HOST="test.localhost")
    assert response.status_code == 200, (path, response.status_code)


@pytest.mark.django_db
@pytest.mark.integration
def test_login_page_available(tenant_ctx, client):
    response = client.get("/accounts/login/", HTTP_HOST="test.localhost")
    assert response.status_code == 200
    assert "Anmelden" in response.content.decode()


@pytest.mark.django_db
@pytest.mark.integration
def test_csv_export_has_bom(tenant_ctx, tenant_client):
    BankAccount.objects.create(name="CSV-Konto", account_type=BankAccount.AccountType.GIRO, balance=10)
    response = tenant_client.get("/export/accounts.csv", HTTP_HOST="test.localhost")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    content = b"".join(response.streaming_content).decode("utf-8")
    assert content.startswith("\ufeffKonto;Typ;IBAN")
    assert "CSV-Konto" in content


@pytest.mark.django_db
@pytest.mark.integration
def test_public_schema_redirects_to_platform(tenant, client):
    response = client.get("/", HTTP_HOST="unknown.example")
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.integration
def test_unauthenticated_redirect(tenant_ctx, client):
    response = client.get("/banking/", HTTP_HOST="test.localhost")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]
