from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core import views as core_views

urlpatterns = [
    path("healthz/", core_views.healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("accounts/login/", core_views.TenantLoginView.as_view(), name="login"),
    path("accounts/logout/", core_views.TenantLogoutView.as_view(), name="logout"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("platform/", include("apps.core.urls")),
    path("", include("apps.cms.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/", include("apps.dashboard.api_urls")),
    path("api/", include("apps.core.api_urls")),
    path("", include("apps.dashboard.urls")),
    path("", include("apps.banking.urls")),
    path("", include("apps.billing.urls")),
    path("", include("apps.erp.urls")),
    path("", include("apps.integrations.urls")),
    path("", include("apps.providers.urls")),
]

if settings.DEBUG or settings.MEDIA_ROOT:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
