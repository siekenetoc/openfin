from django.urls import path

from . import views

app_name = "erp"

urlpatterns = [
    path("erp/", views.erp_dashboard, name="dashboard"),
    path("erp/config/", views.config_edit, name="config_edit"),
    path("erp/config/<int:pk>/", views.config_edit, name="config_edit_pk"),
    path("erp/expected/", views.expected_payment_list, name="expected_list"),
    path("erp/sync-purchases/", views.sync_purchases, name="sync_purchases"),
    path("api/webhooks/erpnext/sales-invoice/", views.sales_invoice_webhook, name="sales_invoice_webhook"),
]
