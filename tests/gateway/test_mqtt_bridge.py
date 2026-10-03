import sys
import types
from unittest.mock import MagicMock

import pytest

# --- Fake paho.mqtt.client (mirrors test_telemetry_logger.py) ----------------
_paho = types.ModuleType("paho")
_paho.__path__ = []
_paho_mqtt = types.ModuleType("paho.mqtt")
_paho_mqtt.__path__ = []
_paho_client = types.ModuleType("paho.mqtt.client")
_paho_client.Client = MagicMock()
_paho_client.CallbackAPIVersion = MagicMock()
sys.modules["paho"] = _paho
sys.modules["paho.mqtt"] = _paho_mqtt
sys.modules["paho.mqtt.client"] = _paho_client

from gateway.api import mqtt_bridge  # noqa: E402
from gateway.api.registry import DeviceRegistry  # noqa: E402


@pytest.fixture
def registry():
    return DeviceRegistry()


# --- handle_message routing --------------------------------------------------


def test_handle_message_status(registry):
    assert mqtt_bridge.handle_message(registry, "dev1/status", b"online") is True
    assert registry.snapshot()[0]["status"] == "online"


def test_handle_message_telemetry(registry):
    topic = "dev1/telemetry"
    payload = b'{"SoilSensor": {"moisture": {"value": 30.0}}}'
    assert mqtt_bridge.handle_message(registry, topic, payload) is True
    assert registry.snapshot()[0]["sensors"]["SoilSensor"]["moisture"]["value"] == 30.0


def test_handle_message_actuator_event(registry):
    topic = "dev1/data/WaterPump/state"
    assert mqtt_bridge.handle_message(registry, topic, b'{"state": "ON"}') is True
    assert registry.snapshot()[0]["actuators"]["WaterPump"] == "ON"


def test_handle_message_malformed_json_is_dropped(registry):
    assert mqtt_bridge.handle_message(registry, "dev1/telemetry", b"not json") is False
    assert registry.snapshot() == []


def test_handle_message_unknown_topic_is_ignored(registry):
    assert mqtt_bridge.handle_message(registry, "dev1/other", b'{"a": 1}') is False


def test_handle_message_on_update_callback_fires_on_change(registry):
    bridge = mqtt_bridge.MqttBridge(
        registry, broker="localhost", port=1883, on_update=MagicMock()
    )
    bridge._on_message(
        None, None, _msg("dev1/telemetry", b'{"SoilSensor": {"moisture": 1}}')
    )
    bridge.on_update.assert_called_once()


def _msg(topic, payload_bytes):
    msg = MagicMock()
    msg.topic = topic
    msg.payload = payload_bytes
    return msg
