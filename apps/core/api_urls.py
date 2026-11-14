from django.urls import path
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Tenant


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "username": request.user.username,
                "email": request.user.email,
                "tenant": request.user.tenant.schema_name if request.user.tenant else None,
                "is_platform_admin": request.user.is_platform_admin,
            }
        )


class TenantListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_platform_admin:
            return Response({"detail": "Nicht erlaubt."}, status=403)
        return Response(
            [
                {
                    "name": tenant.name,
                    "schema_name": tenant.schema_name,
                    "domains": [domain.domain for domain in tenant.domains.all()],
                    "is_active": tenant.is_active,
                }
                for tenant in Tenant.objects.prefetch_related("domains")
            ]
        )


urlpatterns = [
    path("me/", MeView.as_view(), name="api-me"),
    path("tenants/", TenantListView.as_view(), name="api-tenants"),
]
