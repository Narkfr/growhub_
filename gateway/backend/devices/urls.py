from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DeviceViewSet,
    PairingClaimCreateView,
    PairingRedeemView,
    SiteViewSet,
)

router = DefaultRouter(trailing_slash=False)
router.register("sites", SiteViewSet, basename="site")
router.register("devices", DeviceViewSet, basename="device")

urlpatterns = [
    path(
        "devices/claims", PairingClaimCreateView.as_view(), name="pairing-claim-create"
    ),
    path(
        "devices/claims/redeem",
        PairingRedeemView.as_view(),
        name="pairing-claim-redeem",
    ),
    path("", include(router.urls)),
]
