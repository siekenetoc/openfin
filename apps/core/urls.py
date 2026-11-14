from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.platform_home, name="platform_home"),
    path("switch/", views.tenant_switch, name="tenant_switch"),
]
