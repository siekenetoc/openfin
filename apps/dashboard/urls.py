from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("triage/", views.triage, name="triage"),
    path("triage/<int:match_id>/approve/", views.triage_approve, name="triage_approve"),
    path("triage/<int:match_id>/reject/", views.triage_reject, name="triage_reject"),
    path("triage/tx/<int:tx_id>/alternatives/", views.triage_alternatives, name="triage_alternatives"),
    path("export/<str:dataset>.csv", views.export, name="export"),
]
