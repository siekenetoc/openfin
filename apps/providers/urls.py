from django.urls import path

from . import views

app_name = "providers"

urlpatterns = [
    path("providers/", views.provider_dashboard, name="dashboard"),
    path("providers/paypal/<int:pk>/sync/", views.paypal_sync, name="paypal_sync"),
    path("providers/depots/<int:pk>/", views.depot_detail, name="depot_detail"),
    path("providers/depots/<int:pk>/refresh/", views.depot_refresh, name="depot_refresh"),
    path("providers/depots/<int:pk>/positions/new/", views.position_create, name="position_create"),
    path("providers/amazon/<int:pk>/scrape/", views.amazon_scrape, name="amazon_scrape"),
]
