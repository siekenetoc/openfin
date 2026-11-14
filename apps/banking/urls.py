from django.urls import path

from . import views

app_name = "banking"

urlpatterns = [
    path("banking/", views.account_list, name="account_list"),
    path("banking/accounts/new/", views.account_create, name="account_create"),
    path("banking/accounts/<int:pk>/", views.account_detail, name="account_detail"),
    path("banking/accounts/<int:pk>/edit/", views.account_edit, name="account_edit"),
    path("banking/accounts/<int:pk>/sync/", views.account_sync, name="account_sync"),
    path("banking/transactions/", views.transaction_list, name="transaction_list"),
    path("banking/transactions/export/", views.transaction_export, name="transaction_export"),
    path("banking/payments/", views.payment_list, name="payment_list"),
    path("banking/payments/new/", views.payment_create, name="payment_create"),
    path("banking/payments/<int:pk>/", views.payment_detail, name="payment_detail"),
    path("banking/payments/<int:pk>/submit/", views.payment_submit, name="payment_submit"),
    path("banking/payments/<int:pk>/cancel/", views.payment_cancel, name="payment_cancel"),
    path("banking/standing-orders/", views.standing_order_list, name="standing_order_list"),
    path("banking/standing-orders/new/", views.standing_order_create, name="standing_order_create"),
    path("banking/standing-orders/<int:pk>/delete/", views.standing_order_delete, name="standing_order_delete"),
    path("banking/tan/<int:pk>/", views.tan_modal, name="tan_modal"),
    path("banking/tan/<int:pk>/confirm/", views.tan_confirm, name="tan_confirm"),
    path("banking/tan/<int:pk>/cancel/", views.tan_cancel, name="tan_cancel"),
]
