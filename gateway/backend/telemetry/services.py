"""Ingestion of device messages and dispatch of commands.

``handle_message`` is the pure router used by the MQTT worker: it takes a topic
and a raw payload and performs the database side effects. Keeping it free of
any paho object means the whole ingest path is unit-testable.
"""

import json
import logging
import uuid

from devices.models import Device, Membership
from devices.services import sync_capabilities
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from growhub import topics

from .models import CommandAudit, Telemetry
from .serializers import (
    AckPayloadSerializer,
    InfoPayloadSerializer,
    TelemetryPayloadSerializer,
)

logger = logging.getLogger(__name__)


class IngestError(Exception):
    """Raised when a message cannot be attributed or validated."""


class CommandDispatchError(Exception):
    """Raised when a command could not be handed to the broker."""


def split_metric(component, metric, raw):
    """Normalise one metric into ``(value, unit)``.

    Accepts ``{"value": 42, "unit": "percent"}``, a bare number, or ``None``
    (the sensor read failed — stored as a null value so the gap is visible).
    """
    if raw is None:
        return None, ""
    if isinstance(raw, dict):
        unit = raw.get("unit") or ""
        value = raw.get("value")
        if value is None:
            return None, unit
        try:
            return float(value), unit
        except (TypeError, ValueError) as exc:
            raise IngestError(f"{component}.{metric}: valeur non numérique") from exc
    try:
        return float(raw), ""
    except (TypeError, ValueError) as exc:
        raise IngestError(f"{component}.{metric}: valeur non numérique") from exc


def _last_state(device):
    state = device.last_state or {}
    state.setdefault("sensors", {})
    state.setdefault("actuators", {})
    return state


def record_telemetry(device, payload, received_at=None):
    """Store every metric of a telemetry message and refresh the device row."""
    serializer = TelemetryPayloadSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    ts = data.get("ts") or received_at or timezone.now()
    received_at = received_at or timezone.now()
    rows = []
    state = _last_state(device)

    for component, metrics in (data.get("sensors") or {}).items():
        for metric, raw in metrics.items():
            value, unit = split_metric(component, metric, raw)
            rows.append(
                Telemetry(
                    device=device,
                    ts=ts,
                    source=component,
                    metric=metric,
                    value=value,
                    unit=unit,
                )
            )
            state["sensors"].setdefault(component, {})[metric] = {
                "value": value,
                "unit": unit,
            }

    if data.get("actuators"):
        state["actuators"] = dict(data["actuators"])

    state["ts"] = ts.isoformat()
    state["seq"] = data.get("seq")

    with transaction.atomic():
        if rows:
            Telemetry.objects.bulk_create(rows)
        device.last_seen = received_at
        device.last_state = state
        device.save(update_fields=["last_seen", "last_state"])
    return rows


def record_state(device, payload, received_at=None):
    """Retained actuator state: replaces the previous snapshot."""
    state = _last_state(device)
    if isinstance(payload, dict) and "actuators" in payload:
        state["actuators"] = dict(payload["actuators"])
    state["actuators_ts"] = (received_at or timezone.now()).isoformat()
    device.last_state = state
    device.last_seen = received_at or timezone.now()
    device.save(update_fields=["last_state", "last_seen"])


def record_status(device, payload, received_at=None):
    """``status`` topic: ``online`` / ``offline`` (Last Will)."""
    raw = payload.decode() if isinstance(payload, bytes) else str(payload)
    status = raw.strip().strip('"').lower()
    state = _last_state(device)
    state["status"] = status
    state["status_ts"] = (received_at or timezone.now()).isoformat()
    device.last_state = state
    if status == "online":
        device.last_seen = received_at or timezone.now()
        device.save(update_fields=["last_state", "last_seen"])
    else:
        # Keep last_seen untouched: `is_online` then flips as the window expires.
        device.save(update_fields=["last_state"])
    return status


def record_info(device, payload):
    """``info`` topic: declared model, firmware and capabilities."""
    serializer = InfoPayloadSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    return sync_capabilities(device, serializer.validated_data)


def record_ack(payload):
    """``ack`` topic: close a pending command."""
    serializer = AckPayloadSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    audit = CommandAudit.objects.filter(cmd_id=data["cmd_id"]).first()
    if audit is None:
        logger.warning("ack pour une commande inconnue: %s", data["cmd_id"])
        return None
    audit.mark_acked(data["ok"], data.get("error", ""), data.get("state"))
    return audit


def handle_message(topic, payload, received_at=None):
    """Route one MQTT message to its handler.

    Returns ``("kind", result)`` so callers (and tests) can assert what happened.
    Unknown devices are dropped: a device must be paired before it can publish
    anything that matters.
    """
    parts = topic.split("/")
    if len(parts) < 4 or parts[0] != "growhub" or parts[1] != "v1":
        raise IngestError(f"topic hors contrat: {topic}")

    device_id, leaf = parts[2], parts[3]
    # `status` carries a bare word (online/offline); everything else is JSON.
    body = payload if leaf == "status" else _decode(payload)

    if device_id == "provision":
        return handle_provision_message(topic, body)

    device = Device.objects.filter(device_id=device_id).first()
    if device is None:
        raise IngestError(f"appareil inconnu: {device_id}")

    if leaf == "telemetry":
        result = record_telemetry(device, body, received_at)
        _confirm_credentials_if_pending(device)
        return "telemetry", result
    if leaf == "state":
        return "state", record_state(device, body, received_at)
    if leaf == "status":
        return "status", record_status(device, body, received_at)
    if leaf == "info":
        result = record_info(device, body)
        _confirm_credentials_if_pending(device)
        return "info", result
    if leaf == "ack":
        return "ack", record_ack(body)
    raise IngestError(f"topic non géré: {topic}")


def _confirm_credentials_if_pending(device):
    """Finish a pairing handover when the device shows up with its own account.

    Imported lazily: provisioning imports this module's siblings, and we do not
    want an import cycle at module load time.
    """
    from . import provisioning

    try:
        provisioning.maybe_confirm_credentials(device)
    except Exception:  # broker hiccup must never lose a telemetry message
        logger.exception(
            "échec de la confirmation des identifiants de %s", device.device_id
        )


def handle_provision_message(topic, body):
    """Bootstrap messages from a device that is not paired yet (jalon M4)."""
    from .provisioning import record_provisioning_request

    return "provision", record_provisioning_request(topic, body)


def _decode(payload):
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode()
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise IngestError("payload JSON invalide") from exc
    return payload


def _parse_ts(value):
    if not value:
        return None
    return parse_datetime(value)


class CommandDispatcher:
    """Turn an API request into an audited MQTT command."""

    #: kinds a plain member may trigger; configuration stays owner-only.
    MEMBER_KINDS = ("actuators", "sensors")
    #: roles allowed to trigger those kinds (a viewer only reads).
    COMMAND_ROLES = (Membership.Role.OWNER, Membership.Role.MEMBER)

    def __init__(self, publisher):
        self.publisher = publisher

    def can_send(self, device, user, kind):
        if user is None:
            # Internal caller (automation engine): the API always passes a user.
            return True
        role = device.role_of(user)
        if role is None:
            return False
        if kind in self.MEMBER_KINDS:
            return role in self.COMMAND_ROLES
        return role == Membership.Role.OWNER

    def send(self, device, user, kind, action, args=None):
        if kind not in topics.COMMAND_KINDS:
            raise CommandDispatchError(f"type de commande inconnu: {kind}")
        if not self.can_send(device, user, kind):
            raise PermissionError("Action réservée au propriétaire.")

        cmd_id = uuid.uuid4()
        audit = CommandAudit.objects.create(
            device=device,
            user=user if getattr(user, "is_authenticated", False) else None,
            cmd_id=cmd_id,
            kind=kind,
            action=action,
            args=args or {},
        )
        message = {"cmd_id": str(cmd_id), "action": action, "args": args or {}}
        try:
            self.publisher.publish(
                topics.command_topic(device.device_id, kind), message
            )
        except Exception as exc:  # broker down, network error, ...
            audit.status = CommandAudit.Status.FAILED
            audit.error = str(exc)[:255]
            audit.save(update_fields=["status", "error"])
            raise CommandDispatchError(str(exc)) from exc
        return audit


def expire_pending_commands(older_than_seconds=60):
    """Flag commands that were never acknowledged (called by the worker loop)."""
    deadline = timezone.now() - timezone.timedelta(seconds=older_than_seconds)
    return CommandAudit.objects.filter(
        status=CommandAudit.Status.SENT, created_at__lt=deadline
    ).update(status=CommandAudit.Status.TIMEOUT)
