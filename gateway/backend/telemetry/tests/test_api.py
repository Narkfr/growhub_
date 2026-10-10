import asyncio
import json

import pytest
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient
from telemetry.models import CommandAudit, Telemetry
from telemetry.services import handle_message, record_status
from telemetry.views import build_live_snapshot

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def telemetry_message(device, temperature=20.0):
    handle_message(
        f"growhub/v1/{device.device_id}/telemetry",
        {
            "sensors": {"ClimateSensor": {"temperature": temperature}},
            "actuators": {"WaterPump": "OFF"},
        },
    )


def test_live_snapshot_is_scoped_to_memberships(
    auth_client, device, other_user, make_device
):
    telemetry_message(device)
    other_device = make_device(device_id="ghb-001122", owner=other_user)
    telemetry_message(other_device)

    payload = auth_client.get("/api/v1/live").json()
    assert payload["count"] == 1
    assert payload["devices"][0]["device_id"] == device.device_id
    assert (
        payload["devices"][0]["sensors"]["ClimateSensor"]["temperature"]["value"]
        == 20.0
    )
    assert payload["devices"][0]["actuators"] == {"WaterPump": "OFF"}
    assert payload["devices"][0]["is_online"] is True


def test_live_snapshot_requires_authentication(client):
    assert client.get("/api/v1/live").status_code in (401, 403)


def test_telemetry_history_filters_and_scope(
    auth_client, device, other_user, make_device
):
    telemetry_message(device, temperature=19.0)
    telemetry_message(device, temperature=21.0)
    handle_message(
        f"growhub/v1/{device.device_id}/telemetry",
        {"sensors": {"SoilSensor": {"moisture": 40}}},
    )

    payload = auth_client.get(
        f"/api/v1/devices/{device.id}/telemetry", {"metric": "temperature"}
    ).json()
    assert payload["count"] == 2
    assert {point["value"] for point in payload["points"]} == {19.0, 21.0}

    other = make_device(device_id="ghb-001122", owner=other_user)
    assert auth_client.get(f"/api/v1/devices/{other.id}/telemetry").status_code == 404


def test_command_endpoint_sends_and_audits(auth_client, device, monkeypatch, publisher):
    monkeypatch.setattr("telemetry.views.shared_publisher", lambda base: publisher)

    response = auth_client.post(
        f"/api/v1/devices/{device.id}/commands",
        {"kind": "actuators", "action": "ON", "args": {"target": "WaterPump"}},
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "sent"
    assert (
        publisher.messages[0]["topic"] == f"growhub/v1/{device.device_id}/cmd/actuators"
    )
    assert CommandAudit.objects.count() == 1

    history = auth_client.get(f"/api/v1/devices/{device.id}/commands").json()
    assert len(history) == 1
    assert history[0]["cmd_id"] == body["cmd_id"]


def test_command_endpoint_refuses_config_for_members(
    device, other_user, monkeypatch, publisher
):
    device.add_member(other_user, role="member")
    monkeypatch.setattr("telemetry.views.shared_publisher", lambda base: publisher)
    client = APIClient()
    client.force_authenticate(user=other_user)

    response = client.post(
        f"/api/v1/devices/{device.id}/commands",
        {"kind": "config", "action": "SET_INTERVAL", "args": {"seconds": 30}},
        format="json",
    )
    assert response.status_code == 403
    assert CommandAudit.objects.count() == 0


def test_command_endpoint_reports_broker_outage(auth_client, device, monkeypatch):
    class BrokenPublisher:
        def publish(self, *args, **kwargs):
            raise OSError("connexion refusée")

    monkeypatch.setattr(
        "telemetry.views.shared_publisher", lambda base: BrokenPublisher()
    )

    response = auth_client.post(
        f"/api/v1/devices/{device.id}/commands",
        {"kind": "actuators", "action": "ON"},
        format="json",
    )
    assert response.status_code == 503
    assert CommandAudit.objects.get().status == CommandAudit.Status.FAILED


def test_command_endpoint_is_scoped(
    auth_client, other_user, make_device, monkeypatch, publisher
):
    monkeypatch.setattr("telemetry.views.shared_publisher", lambda base: publisher)
    stranger_device = make_device(device_id="ghb-001122", owner=other_user)

    response = auth_client.post(
        f"/api/v1/devices/{stranger_device.id}/commands",
        {"kind": "actuators", "action": "ON"},
        format="json",
    )
    assert response.status_code == 404


def test_live_stream_headers_and_frames(client, user, device, monkeypatch, settings):
    """The stream emits retry, then a data frame, then a keepalive.

    The snapshot builder is stubbed: what is under test here is the streaming
    contract, not the (already covered) database read.
    """
    settings.GROWHUB = {**settings.GROWHUB, "LIVE_POLL_SECONDS": 0.01}
    snapshot = {
        "devices": [{"device_id": device.device_id, "sensors": {}, "actuators": {}}],
        "count": 1,
    }
    monkeypatch.setattr("telemetry.views.build_live_snapshot", lambda _user: snapshot)

    assert client.login(username="marius", password="motdepasse-long-1")
    response = client.get("/api/v1/live/stream", stream=True)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")
    assert response["Cache-Control"] == "no-cache"
    # Un flux compressé se fait bufferiser par le navigateur : plus aucune mesure
    # en direct dans le tableau de bord, alors que l'historique fonctionne.
    assert response["Content-Encoding"] == "identity"

    frames = asyncio.run(_collect_frames(response, 3))
    assert frames[0].startswith("retry: ")
    assert frames[1].startswith("data: ")
    assert json.loads(frames[1][len("data: ") :]) == snapshot
    # Unchanged snapshot -> heartbeat instead of a redundant frame.
    assert frames[2].startswith(": keepalive")


async def _collect_frames(response, count):
    """Read `count` non-empty chunks then stop (the SSE stream never ends)."""
    frames = []
    async for chunk in response.streaming_content:
        text = chunk.decode() if isinstance(chunk, bytes) else chunk
        if text.strip():
            frames.append(text)
        if len(frames) >= count:
            return frames
    raise AssertionError(f"seulement {len(frames)} trame(s) reçue(s)")


def test_live_stream_requires_a_session(client):
    response = client.get("/api/v1/live/stream")
    assert response.status_code == 401


def test_live_snapshot_reports_the_runtime_status(device, user):
    """Le flux annonce l'état d'exécution, pas le cycle de vie de l'appareil.

    Envoyer « provisioned » faisait afficher « Inconnu » sur la carte du tableau de
    bord, alors que le boîtier publie bien `online` / `offline`.
    """
    record_status(device, "online")
    device.refresh_from_db()

    assert build_live_snapshot(user)["devices"][0]["status"] == "online"

    record_status(device, "offline")
    device.refresh_from_db()

    assert build_live_snapshot(user)["devices"][0]["status"] == "offline"


def test_telemetry_ordering_is_newest_first(device, user):
    telemetry_message(device, temperature=1.0)
    telemetry_message(device, temperature=2.0)
    values = list(Telemetry.objects.values_list("value", flat=True))
    assert values[0] == 2.0


def test_three_commands_share_one_mqtt_session(auth_client, device, monkeypatch):
    """Régression : un publicateur MQTT neuf à chaque commande.

    En production, chaque requête ouvrait sa propre session sous un identifiant
    client identique : chacune délogeait la précédente, qui se reconnectait
    aussitôt. Le journal du broker a compté des centaines de connexions par
    minute, jusqu'à faire rejeter comme malformés les paquets du boîtier.
    """
    from telemetry import mqtt

    opened = []

    class CountingPublisher:
        def __init__(self, client_id=None):
            opened.append(client_id)

        def publish(self, topic, payload, retain=False, qos=0):
            return None

    monkeypatch.setattr(mqtt, "_SHARED", {})
    monkeypatch.setattr(mqtt, "MqttPublisher", CountingPublisher)

    for _ in range(3):
        response = auth_client.post(
            f"/api/v1/devices/{device.id}/commands",
            {"kind": "actuators", "action": "ON", "args": {"target": "WaterPump"}},
            format="json",
        )
        assert response.status_code == 201

    assert opened == ["gh-cmd"], "trois commandes, une seule session"


def test_live_snapshot_carries_the_server_clock(user):
    """Le tableau de bord juge la fraîcheur sur l'heure du serveur, pas la sienne.

    `last_seen` est daté par le serveur : le comparer à l'horloge du navigateur
    fait clignoter le badge « Sans nouvelles » dès que les deux montres diffèrent
    — et deux montres diffèrent toujours un peu. L'instantané doit donc annoncer
    l'heure du serveur, que le client prend comme référence.
    """
    before = timezone.now()
    snapshot = build_live_snapshot(user)
    after = timezone.now()

    served = parse_datetime(snapshot["now"])
    assert served is not None
    assert before <= served <= after
