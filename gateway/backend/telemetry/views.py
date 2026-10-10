"""Live state, history, commands and the SSE stream."""

import asyncio
import json
import logging

from asgiref.sync import sync_to_async
from devices.models import Device
from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from django.views import View
from growhub import topics
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import provisioning
from .models import CommandAudit, Telemetry
from .mqtt import shared_publisher
from .provisioning import ProvisioningError
from .serializers import (
    CommandAuditSerializer,
    CommandRequestSerializer,
    TelemetrySerializer,
)
from .services import CommandDispatcher, CommandDispatchError

logger = logging.getLogger(__name__)


def _user_devices(user):
    return (
        Device.objects.for_user(user)
        .select_related("site")
        .prefetch_related("capabilities", "memberships__user")
    )


def build_live_snapshot(user):
    """Serialisable state of every device the user can see (used by SSE too)."""
    devices = []
    for device in _user_devices(user):
        state = device.last_state or {}
        devices.append(
            {
                "id": device.id,
                "device_id": device.device_id,
                "name": device.name,
                "slug": device.slug,
                # Statut d'exécution, pas le cycle de vie : le tableau de bord en
                # déduit « En ligne » / « Hors ligne ». Envoyer `device.status`
                # (« provisioned ») affichait « Inconnu » sur la carte.
                "status": state.get("status")
                or ("online" if device.is_online else "offline"),
                "is_online": device.is_online,
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                "site": device.site.name if device.site else None,
                "sensors": state.get("sensors", {}),
                "actuators": state.get("actuators", {}),
                "ts": state.get("ts"),
            }
        )
    return {"devices": devices, "count": len(devices)}


class LiveSnapshotView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(build_live_snapshot(request.user))


def _sse_frame(payload):
    return f"data: {json.dumps(payload, default=str)}\n\n"


class LiveStreamView(View):
    """Server-sent events: a snapshot, then a frame whenever something changes.

    Plain Django async view (DRF's APIView cannot await an async handler). The
    API process and the MQTT worker are separate, so changes are detected by
    polling the database: a few indexed reads every couple of seconds on a Pi,
    for a handful of devices. Postgres LISTEN/NOTIFY is the upgrade path if this
    ever shows up in profiling.
    """

    async def get(self, request):
        user = await request.auser()
        if not user.is_authenticated:
            return HttpResponse(status=401)
        interval = settings.GROWHUB["LIVE_POLL_SECONDS"]

        async def event_stream():
            yield "retry: 5000\n\n"
            previous = None
            while True:
                try:
                    snapshot = await sync_to_async(build_live_snapshot)(user)
                except Exception:  # user deleted mid-stream, DB hiccup
                    logger.exception("échec de construction du snapshot live")
                    await asyncio.sleep(interval)
                    continue
                if snapshot != previous:
                    previous = snapshot
                    yield _sse_frame(snapshot)
                else:
                    yield ": keepalive\n\n"
                await asyncio.sleep(interval)

        response = StreamingHttpResponse(
            event_stream(), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        # Un flux SSE ne doit jamais être compressé : un compresseur bufferise par
        # blocs, et le navigateur ne voit alors les événements qu'à la fermeture —
        # donc jamais. Constaté en production : 10 octets reçus en 6 s en gzip
        # contre 446 en clair, tableau de bord figé sur « Sans nouvelles » alors
        # que l'historique (appel classique) fonctionnait. Déclarer `identity`
        # empêche le proxy du tableau de bord de recompresser la réponse.
        response["Content-Encoding"] = "identity"
        return response


class TelemetryHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        device = get_object_or_404(_user_devices(request.user), pk=pk)
        queryset = Telemetry.objects.filter(device=device)
        metric = request.query_params.get("metric")
        source = request.query_params.get("source")
        since = parse_datetime(request.query_params.get("since", ""))
        if metric:
            queryset = queryset.filter(metric=metric)
        if source:
            queryset = queryset.filter(source=source)
        if since:
            queryset = queryset.filter(ts__gte=since)
        limit = min(int(request.query_params.get("limit", 200)), 1000)
        points = list(queryset.order_by("-ts")[:limit])
        return Response(
            {
                "device_id": device.device_id,
                "metric": metric,
                "count": len(points),
                "points": TelemetrySerializer(points, many=True).data,
            }
        )


class DeviceCommandView(APIView):
    """POST a command; members may drive actuators, only owners configure."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        device = get_object_or_404(_user_devices(request.user), pk=pk)
        audits = device.commands.select_related("user")[:50]
        return Response(CommandAuditSerializer(audits, many=True).data)

    def post(self, request, pk):
        device = get_object_or_404(_user_devices(request.user), pk=pk)
        payload = CommandRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        dispatcher = CommandDispatcher(publisher=shared_publisher("gh-cmd"))
        try:
            audit = dispatcher.send(
                device,
                request.user,
                payload.validated_data["kind"],
                payload.validated_data["action"],
                payload.validated_data.get("args", {}),
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except CommandDispatchError as exc:
            return Response(
                {"detail": f"Commande non transmise au broker : {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            CommandAuditSerializer(audit).data, status=status.HTTP_201_CREATED
        )


class DeviceProvisionView(APIView):
    """Hand real MQTT credentials to a paired device (staff only).

    The clear-text password is returned once, here, and published to the device
    on its provisioning topic. The database keeps the broker hash only.
    """

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        device = get_object_or_404(Device, pk=pk)
        try:
            credential, password = provisioning.provision_device(device)
        except ProvisioningError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "device_id": device.device_id,
                "username": credential.username,
                "password": password,
                "broker": settings.MQTT_BROKER,
                "port": settings.MQTT_PORT,
                "topic": topics.provision_credentials_topic(device.device_id),
            },
            status=status.HTTP_201_CREATED,
        )


class DeviceProvisionRevokeView(APIView):
    """Cut a device off the broker (staff only)."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        device = get_object_or_404(Device, pk=pk)
        credential = provisioning.revoke_credentials(device)
        return Response(
            {
                "device_id": device.device_id,
                "revoked_at": credential.revoked_at if credential else None,
            }
        )


class CommandHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        device_pk = request.query_params.get("device")
        audits = CommandAudit.objects.filter(
            device__in=_user_devices(request.user)
        ).select_related("user")
        if device_pk:
            audits = audits.filter(device_id=device_pk)
        return Response(CommandAuditSerializer(audits[:100], many=True).data)
