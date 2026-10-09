"""Root URL configuration: admin, API v1 and (temporary) health endpoint."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok", "service": "growhub-backend"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", health, name="health"),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/", include("devices.urls")),
]
