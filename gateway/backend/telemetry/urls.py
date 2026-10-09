from django.urls import path

from .views import (
    CommandHistoryView,
    DeviceCommandView,
    DeviceProvisionRevokeView,
    DeviceProvisionView,
    LiveSnapshotView,
    LiveStreamView,
    TelemetryHistoryView,
)

urlpatterns = [
    path("live", LiveSnapshotView.as_view(), name="live-snapshot"),
    path("live/stream", LiveStreamView.as_view(), name="live-stream"),
    path("commands", CommandHistoryView.as_view(), name="command-history"),
    path(
        "devices/<int:pk>/commands", DeviceCommandView.as_view(), name="device-commands"
    ),
    path(
        "devices/<int:pk>/telemetry",
        TelemetryHistoryView.as_view(),
        name="device-telemetry",
    ),
    path(
        "devices/<int:pk>/provision",
        DeviceProvisionView.as_view(),
        name="device-provision",
    ),
    path(
        "devices/<int:pk>/provision/revoke",
        DeviceProvisionRevokeView.as_view(),
        name="device-provision-revoke",
    ),
]
