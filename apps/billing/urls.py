from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("billing/collections/", views.collection_dashboard, name="collection_dashboard"),
    path("billing/mandates/", views.mandate_list, name="mandate_list"),
    path("billing/mandates/new/", views.mandate_create, name="mandate_create"),
    path("billing/mandates/<int:pk>/edit/", views.mandate_edit, name="mandate_edit"),
    path("billing/sepa/new/", views.sepa_batch_new, name="sepa_batch_new"),
    path("billing/sepa/<int:pk>/", views.sepa_batch_detail, name="sepa_batch_detail"),
    path("billing/sepa/<int:pk>/download/", views.sepa_batch_download, name="sepa_batch_download"),
    path("billing/sepa/<int:pk>/submit/", views.sepa_batch_submit, name="sepa_batch_submit"),
    path("billing/sepa/<int:pk>/prenotify/", views.sepa_batch_prenotify, name="sepa_batch_prenotify"),
    path("billing/payment-links/", views.payment_link_list, name="payment_link_list"),
    path("billing/payment-links/create/", views.payment_link_create, name="payment_link_create"),
    path("billing/providers/", views.provider_config, name="provider_config"),
    path("billing/success/", views.payment_success, name="payment_success"),
    path("billing/cancelled/", views.payment_cancelled, name="payment_cancelled"),
    path("api/webhooks/payments/<str:provider>/", views.payment_webhook, name="payment_webhook"),
]
