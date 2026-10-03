import json
import queue
import time

from gateway.api.registry import (
    DeviceRegistry,
    EventHub,
    normalize_metric,
    parse_telemetry,
)
from gateway.api.state import iter_events, state_payload

# --- normalize_metric --------------------------------------------------------


def test_normalize_metric_dict():
    assert normalize_metric({"value": 18, "unit": "celsius"}) == {
        "value": 18,
        "unit": "celsius",
    }


def test_normalize_metric_bare_number():
    assert normalize_metric(33) == {"value": 33, "unit": None}


def test_normalize_metric_none():
    assert normalize_metric(None) is None


def test_normalize_metric_dict_without_value():
    assert normalize_metric({"unit": "celsius"}) is None


# --- parse_telemetry ---------------------------------------------------------


def test_parse_telemetry_full_payload():
    payload = {
        "ClimateSensor": {
            "temperature": {"value": 18, "unit": "celsius"},
            "humidity": {"value": 55, "unit": "percent"},
        },
        "SoilSensor": {"moisture": {"value": 42, "unit": "percent"}},
        "actuators": {"WaterPump": "ON", "GrowLamp": "OFF"},
    }
    sensors, actuators = parse_telemetry(payload)
    assert sensors["ClimateSensor"]["temperature"]["value"] == 18
    assert sensors["SoilSensor"]["moisture"]["value"] == 42
    assert actuators == {"WaterPump": "ON", "GrowLamp": "OFF"}


def test_parse_telemetry_skips_failed_sensor_and_actuators_key():
    sensors, actuators = parse_telemetry(
        {"ClimateSensor": None, "SoilSensor": {"moisture": 20}, "actuators": {}}
    )
    assert "ClimateSensor" not in sensors
    assert sensors["SoilSensor"]["moisture"]["value"] == 20
    assert actuators == {}


def test_parse_telemetry_non_dict_sensor_is_dropped():
    sensors, _ = parse_telemetry({"SoilSensor": "not-a-dict"})
    assert sensors == {}


def test_parse_telemetry_normalizes_actuator_state_to_on_off():
    _, actuators = parse_telemetry({"actuators": {"Pump": "on", "Lamp": "OFF"}})
    assert actuators == {"Pump": "OFF", "Lamp": "OFF"}


# --- DeviceRegistry ----------------------------------------------------------


def test_registry_telemetry_creates_device_and_marks_online():
    reg = DeviceRegistry()
    reg.apply_telemetry(
        "dev1", {"SoilSensor": {"moisture": {"value": 42, "unit": "percent"}}}
    )
    devs = reg.snapshot()
    assert len(devs) == 1
    dev = devs[0]
    assert dev["id"] == "dev1"
    assert dev["status"] == "online"
    assert dev["last_seen"] is not None
    assert dev["sensors"]["SoilSensor"]["moisture"]["value"] == 42


def test_registry_actuator_event_updates_only_target():
    reg = DeviceRegistry()
    reg.apply_telemetry("dev1", {"actuators": {"WaterPump": "OFF", "GrowLamp": "OFF"}})
    reg.apply_actuator_event("dev1", "WaterPump", {"state": "ON"})
    dev = reg.snapshot()[0]
    assert dev["actuators"] == {"WaterPump": "ON", "GrowLamp": "OFF"}


def test_registry_status_online_offline_and_garbage():
    reg = DeviceRegistry()
    reg.apply_status("dev1", b"online")
    assert reg.snapshot()[0]["status"] == "online"
    reg.apply_status("dev1", b"OFFLINE")
    assert reg.snapshot()[0]["status"] == "offline"
    reg.apply_status("dev1", b"something-else")
    assert reg.snapshot()[0]["status"] == "offline"


def test_registry_snapshot_sorted_and_isolated():
    reg = DeviceRegistry()
    reg.apply_status("dev-b", b"online")
    reg.apply_status("dev-a", b"online")
    snap = reg.snapshot()
    assert [d["id"] for d in snap] == ["dev-a", "dev-b"]
    snap[0]["status"] = "offline"  # mutate the returned copy
    assert reg.snapshot()[0]["status"] == "online"


# --- state_payload -----------------------------------------------------------


def test_state_payload_shape():
    reg = DeviceRegistry()
    reg.apply_status("dev1", b"online")
    payload = state_payload(reg)
    assert payload["count"] == 1
    assert payload["devices"][0]["id"] == "dev1"


# --- EventHub ----------------------------------------------------------------


def test_event_hub_publish_subscribe_unsubscribe():
    hub = EventHub()
    q1 = hub.subscribe()
    q2 = hub.subscribe()
    hub.publish({"x": 1})
    assert q1.get(timeout=1) == {"x": 1}
    assert q2.get(timeout=1) == {"x": 1}
    hub.unsubscribe(q1)
    hub.publish({"y": 2})
    assert q2.get(timeout=1) == {"y": 2}
    assert q1.empty()


# --- iter_events -------------------------------------------------------------


def test_iter_events_snapshot_then_update():
    reg = DeviceRegistry()
    reg.apply_status("dev1", b"online")
    q = queue.Queue()
    gen = iter_events(reg, q)

    snapshot = next(gen)
    assert "dev1" in snapshot

    update = {"devices": [], "count": 0}
    q.put(update)
    assert next(gen) == f"data: {json.dumps(update)}\n\n"


def test_iter_events_keepalive_on_timeout():
    reg = DeviceRegistry()
    q = queue.Queue()
    gen = iter_events(reg, q, heartbeat_seconds=0)
    next(gen)  # initial snapshot
    assert next(gen) == ": keepalive\n\n"


def test_state_payload_drops_stale_devices():
    now = time.time()

    class FakeRegistry:
        def snapshot(self):
            return [
                {
                    "id": "fresh",
                    "status": "online",
                    "last_seen": now - 10,
                    "sensors": {},
                    "actuators": {},
                },
                {
                    "id": "stale",
                    "status": "online",
                    "last_seen": now - 600,
                    "sensors": {},
                    "actuators": {},
                },
                {
                    "id": "never",
                    "status": "unknown",
                    "last_seen": None,
                    "sensors": {},
                    "actuators": {},
                },
            ]

    payload = state_payload(FakeRegistry(), stale_after=300)
    assert [d["id"] for d in payload["devices"]] == ["fresh"]
    assert payload["count"] == 1
