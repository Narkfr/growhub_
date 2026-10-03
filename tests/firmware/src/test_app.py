import asyncio
import binascii
import json as _json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Make `src` and `constants` importable as top-level packages (as on the Pico)
_FIRMWARE = Path(__file__).resolve().parents[3] / "firmware"
sys.path.insert(0, str(_FIRMWARE))

# --- Mock MicroPython hardware/network modules -------------------------------
_machine = MagicMock()
_machine.unique_id.return_value = b"\x01\x02\x03\x04\x05\x06\x07\x08"
sys.modules["machine"] = _machine

_ubinascii = types.ModuleType("ubinascii")
_ubinascii.hexlify = binascii.hexlify
sys.modules["ubinascii"] = _ubinascii

_ujson = types.ModuleType("ujson")
_ujson.dumps = _json.dumps
sys.modules["ujson"] = _ujson

_dht = MagicMock()
sys.modules["dht"] = _dht

_network = MagicMock()
_network.STA_IF = 0
sys.modules["network"] = _network


async def _noop(_s):
    return None


_uasyncio = types.ModuleType("uasyncio")
_uasyncio.sleep = _noop
sys.modules["uasyncio"] = _uasyncio

_lib = types.ModuleType("lib")
_lib.__path__ = []
_umqtt = types.ModuleType("lib.umqtt")
_umqtt.__path__ = []
_simple = types.ModuleType("lib.umqtt.simple")
_simple.MQTTClient = MagicMock
_simple.MQTTException = type("MQTTException", (Exception,), {})
sys.modules["lib"] = _lib
sys.modules["lib.umqtt"] = _umqtt
sys.modules["lib.umqtt.simple"] = _simple

# --- Fake actuator / button / sensor classes ---------------------------------


class FakeActuator:
    def __init__(self, pin, actuator_id, active_low=True):
        self.pin = pin
        self.id = actuator_id
        self.active_low = active_low
        self.on = MagicMock()
        self.off = MagicMock()
        self.toggle = MagicMock()
        self.is_on = MagicMock(return_value=False)
        self.human_state = MagicMock(return_value="OFF")


class FakeButton:
    def __init__(self, pin, button_id, target_id):
        self.pin = pin
        self.id = button_id
        self.target_id = target_id
        self.is_pressed = MagicMock(return_value=False)


class FakeSensor:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.read = MagicMock(return_value={"v": 1})


# Override app.py's direct dependencies with fakes
_act_base = types.ModuleType("src.actuators.base")
_act_base.BaseActuator = FakeActuator
_act_base.ManualButton = FakeButton
sys.modules["src.actuators.base"] = _act_base

_mqtt_mod = types.ModuleType("src.mqtt_manager")
_mqtt_mod.MqttManager = MagicMock
sys.modules["src.mqtt_manager"] = _mqtt_mod

_net_mod = types.ModuleType("src.network_manager")


class FakeNetworkManager:
    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.wlan = MagicMock()


_net_mod.NetworkManager = FakeNetworkManager
sys.modules["src.network_manager"] = _net_mod

_sensor_classes = types.ModuleType("src.sensors.sensor_classes")
_sensor_classes.SENSOR_CLASSES = {"csmsv2": FakeSensor, "dht11": FakeSensor}
sys.modules["src.sensors.sensor_classes"] = _sensor_classes

_display = types.ModuleType("src.display")
_display.Display = MagicMock()
sys.modules["src.display"] = _display

from src.app import GrowHubController  # noqa: E402

MANIFEST = {
    "client_id": "GrowHubClient",
    "actuators": [{"id": "Pump", "pin": 18, "active_low": True}],
    "buttons": [{"id": "PumpButton", "pin": 14, "target": "Pump"}],
    "sensors": [
        {
            "id": "Soil",
            "type": "csmsv2",
            "pin": 26,
            "calibration": {"dry": 50000, "wet": 18000},
        },
        {"id": "Climate", "type": "dht11", "pin": 15},
    ],
}
SECRETS = {
    "WIFI_SSID": "ssid",
    "WIFI_PASSWORD": "pw",
    "MQTT_BROKER": "broker",
    "MQTT_USER": "u",
    "MQTT_PASSWORD": "p",
    "MQTT_PORT": 1883,
}


async def _instant_sleep(*args, **kwargs):
    return None


class _LoopBreak(Exception):
    pass


async def _break_sleep(*args, **kwargs):
    raise _LoopBreak()


@pytest.fixture
def controller():
    return GrowHubController(MANIFEST, SECRETS)


# --- construction ------------------------------------------------------------


def test_client_id_derived_from_unique_id(controller):
    assert controller.client_id == "GrowHubClient-0102030405060708"


def test_setup_hardware_populates(controller):
    assert set(controller.actuators) == {"Pump"}
    assert set(controller.sensors) == {"Soil", "Climate"}
    assert [b.id for b in controller.buttons] == ["PumpButton"]


def test_setup_hardware_passes_calibration(controller):
    soil = controller.sensors["Soil"]
    assert soil.kwargs["pin_number"] == 26
    assert soil.kwargs["calibration"] == {"dry": 50000, "wet": 18000}


def test_setup_hardware_ignores_unknown_sensor_type():
    m = dict(MANIFEST, sensors=[{"id": "X", "type": "nope", "pin": 1}])
    c = GrowHubController(m, SECRETS)
    assert c.sensors == {}


def test_setup_hardware_active_low_default():
    m = dict(
        MANIFEST,
        actuators=[{"id": "Pump", "pin": 18}],  # no active_low -> default True
    )
    c = GrowHubController(m, SECRETS)
    assert c.actuators["Pump"].active_low is True


# --- _on_message routing -----------------------------------------------------


def test_on_message_actuator_on(controller):
    controller._on_message(b"dev/actuators/Pump/action", b"on")
    controller.actuators["Pump"].on.assert_called_once()


def test_on_message_actuator_feedback_topic(controller):
    controller.actuators["Pump"].human_state.return_value = "ON"
    controller._on_message(b"dev/actuators/Pump/action", b"on")
    topic = controller.mqtt.publish.call_args[0][0]
    assert topic == f"{controller.client_id}/data/Pump/state"


def test_on_message_actuator_feedback_retained(controller):
    controller._on_message(b"dev/actuators/Pump/action", b"on")
    assert controller.mqtt.publish.call_args[1] == {"retain": True}


def test_on_message_actuator_disallowed_action(controller):
    controller._on_message(b"dev/actuators/Pump/action", b"explode")
    controller.actuators["Pump"].on.assert_not_called()
    controller.actuators["Pump"].off.assert_not_called()


def test_on_message_short_topic_ignored(controller):
    controller._on_message(b"dev/actuators", b"on")
    controller.mqtt.publish.assert_not_called()


def test_on_message_unknown_actuator(controller):
    controller._on_message(b"dev/actuators/Nope/action", b"on")
    controller.mqtt.publish.assert_not_called()


def test_on_message_sensor_read(controller):
    controller.sensors["Soil"].read.return_value = {"moisture": {"value": 50.0}}
    controller._on_message(b"dev/sensors/Soil/action", b"read")
    controller.sensors["Soil"].read.assert_called_once()
    topic, payload = controller.mqtt.publish.call_args[0]
    assert topic == f"{controller.client_id}/telemetry"
    assert payload == {"Soil": {"moisture": {"value": 50.0}}}


def test_on_message_sensor_read_none_skipped(controller):
    controller.sensors["Soil"].read.return_value = None
    controller._on_message(b"dev/sensors/Soil/action", b"read")
    controller.mqtt.publish.assert_not_called()


# --- _read_sensor ------------------------------------------------------------


def test_read_sensor_first_try(controller):
    sensor = controller.sensors["Soil"]
    sensor.read.return_value = {"moisture": {"value": 1}}
    result = asyncio.run(controller._read_sensor(sensor))
    assert result == {"moisture": {"value": 1}}
    assert sensor.read.call_count == 1


def test_read_sensor_retries_on_none(controller):
    sensor = controller.sensors["Climate"]
    sensor.read.side_effect = [None, None, {"temperature": {"value": 20}}]
    with patch("asyncio.sleep", _instant_sleep):
        result = asyncio.run(controller._read_sensor(sensor))
    assert result == {"temperature": {"value": 20}}
    assert sensor.read.call_count == 3


def test_read_sensor_exhausts_retries(controller):
    sensor = controller.sensors["Climate"]
    sensor.read.return_value = None
    with patch("asyncio.sleep", _instant_sleep):
        result = asyncio.run(controller._read_sensor(sensor, retries=2))
    assert result is None
    assert sensor.read.call_count == 2


def test_read_sensor_recovers_from_exception(controller):
    sensor = controller.sensors["Soil"]
    sensor.read.side_effect = [OSError("fail"), {"moisture": {"value": 5}}]
    with patch("asyncio.sleep", _instant_sleep):
        result = asyncio.run(controller._read_sensor(sensor))
    assert result == {"moisture": {"value": 5}}
    assert sensor.read.call_count == 2


# --- loop tasks --------------------------------------------------------------


def test_telemetry_task_publishes(controller):
    controller.wifi.wlan.isconnected.return_value = True
    controller.mqtt.is_connected.return_value = True
    controller.sensors["Soil"].read.return_value = {"moisture": {"value": 42.0}}
    controller.sensors["Climate"].read.return_value = {"temperature": {"value": 20}}
    controller.actuators["Pump"].is_on.return_value = True

    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(controller._telemetry_task())

    controller.mqtt.publish.assert_called_once()
    topic, data = controller.mqtt.publish.call_args[0]
    assert topic == f"{controller.client_id}/telemetry"
    assert data["Soil"] == {"moisture": {"value": 42.0}}
    assert data["Climate"] == {"temperature": {"value": 20}}
    assert data["actuators"] == {"Pump": "ON"}


def test_telemetry_task_skips_when_disconnected(controller):
    controller.wifi.wlan.isconnected.return_value = False
    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(controller._telemetry_task())
    controller.mqtt.publish.assert_not_called()


def test_listen_task_calls_check_msg(controller):
    controller.wifi.wlan.isconnected.return_value = True
    controller.mqtt.is_connected.return_value = True
    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(controller._listen_task())
    controller.mqtt.check_msg.assert_called_once()


def test_button_task_toggles_pressed(controller):
    btn = controller.buttons[0]
    btn.is_pressed.return_value = True
    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(controller._button_task())
    controller.actuators["Pump"].toggle.assert_called_once()
    controller.mqtt.publish.assert_called_once()


def test_button_task_ignores_unpressed(controller):
    controller.buttons[0].is_pressed.return_value = False
    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(controller._button_task())
    controller.actuators["Pump"].toggle.assert_not_called()
    controller.mqtt.publish.assert_not_called()


def test_mqtt_keepalive_reconnects(controller):
    controller.wifi.wlan.isconnected.return_value = True
    controller.mqtt.is_connected.return_value = False
    controller.mqtt.connect = AsyncMock()
    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(controller._mqtt_keepalive())
    controller.mqtt.connect.assert_called_once()


# --- display integration -----------------------------------------------------


def test_setup_display_when_configured():
    _display.Display.reset_mock()
    display_cfg = {"type": "ssd1306", "width": 128, "height": 64}
    c = GrowHubController(dict(MANIFEST, display=display_cfg), SECRETS)
    assert c.display is _display.Display.return_value
    _display.Display.assert_called_once_with(display_cfg)


def test_setup_display_absent():
    c = GrowHubController(MANIFEST, SECRETS)
    assert c.display is None


def test_display_task_returns_when_no_display():
    c = GrowHubController(MANIFEST, SECRETS)
    asyncio.run(c._display_task())


def test_display_task_renders_temperature():
    c = GrowHubController(MANIFEST, SECRETS)
    c.display = MagicMock()
    c.sensors["Climate"].read.return_value = {
        "temperature": {"value": 21.5},
        "humidity": {"value": 55},
    }
    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(c._display_task())

    c.display.clear.assert_called_once()
    c.display.text.assert_any_call("GROWHUB", 0, 0)
    c.display.text.assert_any_call("Temp: 21.5 C", 0, 25)
    c.display.text.assert_any_call("Hum: 55%", 0, 45)
    c.display.show.assert_called_once()


def test_display_task_shows_error_when_no_temperature():
    c = GrowHubController(MANIFEST, SECRETS)
    c.display = MagicMock()
    for sensor in c.sensors.values():
        sensor.read.return_value = {"moisture": {"value": 40}}
    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(c._display_task())
    c.display.text.assert_any_call("Erreur Capteur", 0, 25)
