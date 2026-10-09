import json

import pytest
from devices.models import Capability
from telemetry.models import CommandAudit, Telemetry
from telemetry.services import IngestError, handle_message

pytestmark = pytest.mark.django_db

TELEMETRY_TOPIC = "growhub/v1/ghb-3f2a91/telemetry"


def test_telemetry_message_is_stored(device):
    payload = {
        "ts": "2026-10-09T12:00:00Z",
        "seq": 7,
        "sensors": {
            "ClimateSensor": {
                "temperature": {"value": 21.5, "unit": "celsius"},
                "humidity": 62,
            },
            "SoilSensor": {"moisture": None},
        },
        "actuators": {"WaterPump": "ON"},
    }
    kind, rows = handle_message(TELEMETRY_TOPIC, json.dumps(payload))

    assert kind == "telemetry"
    assert len(rows) == 3
    device.refresh_from_db()
    assert device.last_seen is not None
    assert device.last_state["actuators"] == {"WaterPump": "ON"}
    assert device.last_state["sensors"]["ClimateSensor"]["temperature"] == {
        "value": 21.5,
        "unit": "celsius",
    }
    assert device.last_state["seq"] == 7

    stored = {row.metric: row for row in Telemetry.objects.filter(device=device)}
    assert stored["temperature"].value == 21.5
    assert stored["temperature"].unit == "celsius"
    assert stored["humidity"].value == 62.0
    assert stored["moisture"].value is None


def test_telemetry_accepts_bytes_and_naive_timestamps(device):
    payload = json.dumps(
        {
            "sensors": {"ClimateSensor": {"temperature": 18}},
            "ts": "2026-10-09T12:00:00+00:00",
        }
    ).encode()
    kind, rows = handle_message(TELEMETRY_TOPIC, payload)
    assert kind == "telemetry"
    assert rows[0].ts.tzinfo is not None


def test_telemetry_rejects_broken_payload(device):
    with pytest.raises(IngestError):
        handle_message(TELEMETRY_TOPIC, "{pas du json")
    with pytest.raises(IngestError):
        handle_message(
            TELEMETRY_TOPIC,
            json.dumps({"sensors": {"ClimateSensor": {"temp": "haut"}}}),
        )


def test_unknown_device_is_rejected(db):
    with pytest.raises(IngestError):
        handle_message("growhub/v1/ghb-ffffff/telemetry", {"sensors": {}})


def test_topic_outside_the_contract_is_rejected(device):
    with pytest.raises(IngestError):
        handle_message("growhub/v2/ghb-3f2a91/telemetry", {"sensors": {}})
    with pytest.raises(IngestError):
        handle_message("growhub/v1/ghb-3f2a91/inconnu", {})


def test_state_message_replaces_actuators(device):
    handle_message(
        TELEMETRY_TOPIC, {"actuators": {"WaterPump": "OFF", "GrowLamp": "ON"}}
    )
    kind, _ = handle_message(
        "growhub/v1/ghb-3f2a91/state", {"actuators": {"WaterPump": "ON"}}
    )

    assert kind == "state"
    device.refresh_from_db()
    assert device.last_state["actuators"] == {"WaterPump": "ON"}


def test_status_online_updates_last_seen_and_offline_keeps_it(device):
    kind, status = handle_message("growhub/v1/ghb-3f2a91/status", b"online")
    assert (kind, status) == ("status", "online")
    device.refresh_from_db()
    seen = device.last_seen
    assert seen is not None
    assert device.last_state["status"] == "online"

    handle_message("growhub/v1/ghb-3f2a91/status", b"offline")
    device.refresh_from_db()
    assert device.last_seen == seen
    assert device.last_state["status"] == "offline"


def test_info_message_declares_capabilities(device):
    payload = {
        "model": "Bourgeon V1",
        "fw": "2.0.0",
        "sensors": [{"name": "ClimateSensor", "metrics": ["temperature"]}],
        "actuators": [{"name": "WaterPump"}],
    }
    kind, capabilities = handle_message("growhub/v1/ghb-3f2a91/info", payload)

    assert kind == "info"
    assert len(capabilities) == 2
    device.refresh_from_db()
    assert device.fw_version == "2.0.0"
    assert device.capabilities.filter(kind=Capability.Kind.ACTUATOR).count() == 1


def test_ack_updates_the_command_audit(device, user):
    audit = CommandAudit.objects.create(
        device=device,
        user=user,
        cmd_id="6f1c3a56-0f6d-4b6b-9a2e-2f6f0d5b0f11",
        kind="actuators",
        action="ON",
    )
    payload = {"cmd_id": str(audit.cmd_id), "ok": True, "state": {"WaterPump": "ON"}}
    kind, updated = handle_message("growhub/v1/ghb-3f2a91/ack", payload)

    assert kind == "ack"
    assert updated.status == CommandAudit.Status.ACKED
    assert updated.acked_at is not None


def test_ack_for_unknown_command_is_ignored(device):
    kind, result = handle_message(
        "growhub/v1/ghb-3f2a91/ack",
        {"cmd_id": "6f1c3a56-0f6d-4b6b-9a2e-2f6f0d5b0f99", "ok": True},
    )
    assert kind == "ack"
    assert result is None


def test_retained_duplicate_telemetry_same_second_does_not_crash(device):
    payload = {"sensors": {"ClimateSensor": {"temperature": 20}}}
    handle_message(TELEMETRY_TOPIC, payload)
    handle_message(TELEMETRY_TOPIC, payload)
    assert Telemetry.objects.filter(device=device).count() == 2


def test_provisioning_message_from_unknown_device_is_recorded_and_ignored(db):
    kind, result = handle_message(
        "growhub/v1/provision/ghb-abcdef", {"model": "Bourgeon V1", "hw_id": "abcdef"}
    )
    assert kind == "provision"
    assert result["known"] is False


def test_device_cannot_publish_on_its_credentials_topic(device):
    with pytest.raises(ValueError):
        handle_message("growhub/v1/provision/ghb-3f2a91/creds", {"username": "x"})
