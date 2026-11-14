from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    path("integrations/", views.integrations_dashboard, name="dashboard"),
    path("integrations/datev/config/", views.datev_config, name="datev_config"),
    path("integrations/datev/export/", views.datev_export, name="datev_export"),
    path("integrations/paperless/autolink/", views.paperless_autolink_all, name="paperless_autolink"),
    path("integrations/paperless/<int:pk>/link/", views.paperless_link_transaction, name="paperless_link"),
    path("integrations/ai/categorize/<int:pk>/", views.ai_categorize_transaction, name="ai_categorize"),
    path("integrations/ai/categorize-batch/", views.ai_categorize_batch, name="ai_categorize_batch"),
    path("integrations/ai/query/", views.ai_query, name="ai_query"),
]
