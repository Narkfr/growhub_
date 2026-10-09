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
_ujson.loads = _json.loads
_ujson.load = _json.load
_ujson.dump = _json.dump
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
_simple.MQTTClient = MagicMock()
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

# `src.display` (Display simulé + vrai ScreenLayout) vient de conftest.py.

from src.app import GrowHubController  # noqa: E402

DEVICE = "ghb-3f2a91"
BOOTSTRAP_USER = "boot-ghb-3f2a91"

DISPLAY_CONFIG = {"type": "ssd1306", "width": 128, "height": 64}

MANIFEST = {
    "model": "Bourgeon V1",
    "display": DISPLAY_CONFIG,
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
    "MQTT_USER": BOOTSTRAP_USER,
    "MQTT_PASSWORD": "bootstrap-pw",
    "MQTT_PORT": 1883,
    "DEVICE_ID": DEVICE,
    "PAIRING_CODE": "ABC234",
}
STORED_CREDENTIALS = {
    "username": DEVICE,
    "password": "device-pw",
    "broker": "broker",
    "port": 1883,
}


async def _instant_sleep(*args, **kwargs):
    return None


class _LoopBreak(Exception):
    pass


async def _break_sleep(*args, **kwargs):
    raise _LoopBreak()


def _creds_path(tmp_path):
    return str(tmp_path / "creds.json")


@pytest.fixture
def unpaired(tmp_path):
    """Boîtier neuf : compte d'amorçage, aucun identifiant définitif."""
    return GrowHubController(MANIFEST, SECRETS, credentials_path=_creds_path(tmp_path))


@pytest.fixture
def controller(tmp_path):
    """Boîtier déjà appairé : identifiants définitifs sur la carte."""
    path = Path(_creds_path(tmp_path))
    path.write_text(_json.dumps(STORED_CREDENTIALS))
    return GrowHubController(MANIFEST, SECRETS, credentials_path=str(path))


def cmd_payload(action, **args):
    return {"cmd_id": "c1", "action": action, "args": args}


def topic(category):
    return f"growhub/v1/{DEVICE}/cmd/{category}"


def raw(payload):
    return _json.dumps(payload).encode()


# --- identité et mode --------------------------------------------------------


def test_device_id_comes_from_secrets_when_provisioned(controller):
    assert controller.device_id == DEVICE


def test_device_id_derived_from_hardware_without_secrets(tmp_path):
    c = GrowHubController(MANIFEST, {}, credentials_path=_creds_path(tmp_path))
    assert c.device_id == "ghb-060708"


def test_new_device_starts_in_pairing_mode(unpaired):
    assert unpaired.pairing is True
    assert unpaired.credentials["username"] == BOOTSTRAP_USER


def test_paired_device_uses_stored_credentials(controller):
    assert controller.pairing is False
    assert controller.credentials["username"] == DEVICE


def test_broker_client_built_with_current_credentials(unpaired, controller):
    assert unpaired.mqtt.device_id == DEVICE
    assert controller.mqtt.device_id == DEVICE
    assert controller.mqtt.broker_ip == "broker"


def test_credentials_topic_subscribed_only_while_pairing(unpaired, controller):
    assert f"growhub/v1/provision/{DEVICE}/creds" in unpaired._subscriptions()
    assert f"growhub/v1/provision/{DEVICE}/creds" not in controller._subscriptions()
    assert topic("config") in controller._subscriptions()


# --- construction ------------------------------------------------------------


def test_setup_hardware_populates(controller):
    assert set(controller.actuators) == {"Pump"}
    assert set(controller.sensors) == {"Soil", "Climate"}
    assert [b.id for b in controller.buttons] == ["PumpButton"]


def test_setup_hardware_passes_calibration(controller):
    soil = controller.sensors["Soil"]
    assert soil.kwargs["pin_number"] == 26
    assert soil.kwargs["calibration"] == {"dry": 50000, "wet": 18000}


def test_setup_hardware_ignores_unknown_sensor_type(tmp_path):
    m = dict(MANIFEST, sensors=[{"id": "X", "type": "nope", "pin": 1}])
    c = GrowHubController(m, SECRETS, credentials_path=_creds_path(tmp_path))
    assert c.sensors == {}


def test_setup_hardware_active_low_default(tmp_path):
    m = dict(MANIFEST, actuators=[{"id": "Pump", "pin": 18}])
    c = GrowHubController(m, SECRETS, credentials_path=_creds_path(tmp_path))
    assert c.actuators["Pump"].active_low is True


def test_telemetry_interval_default(controller):
    assert controller.telemetry_interval == 30


# --- commandes d'actionneurs -------------------------------------------------


def test_actuator_command_runs_the_action(controller):
    controller._on_message(
        topic("actuators").encode(), raw(cmd_payload("on", target="Pump"))
    )
    controller.actuators["Pump"].on.assert_called_once()


def test_actuator_command_accepts_lower_and_upper_case(controller):
    controller._on_message(topic("actuators"), cmd_payload("ON", target="Pump"))
    controller.actuators["Pump"].on.assert_called_once()


def test_actuator_command_publishes_retained_state(controller):
    controller.actuators["Pump"].human_state.return_value = "ON"
    controller._on_message(topic("actuators"), cmd_payload("on", target="Pump"))
    published = {call[0][0]: call for call in controller.mqtt.publish.call_args_list}
    state_call = published[f"growhub/v1/{DEVICE}/state"]
    assert state_call[0][1] == {"actuators": {"Pump": "ON"}}
    assert state_call[1]["retain"] is True


def test_actuator_command_acks_success(controller):
    controller.actuators["Pump"].human_state.return_value = "ON"
    controller._on_message(topic("actuators"), cmd_payload("on", target="Pump"))
    ack = controller.mqtt.publish.call_args_list[-1][0]
    assert ack[0] == f"growhub/v1/{DEVICE}/ack"
    assert ack[1] == {
        "cmd_id": "c1",
        "ok": True,
        "error": "",
        "state": {"actuators": {"Pump": "ON"}},
    }


def test_actuator_command_refuses_unknown_action(controller):
    controller._on_message(topic("actuators"), cmd_payload("explode", target="Pump"))
    controller.actuators["Pump"].on.assert_not_called()
    ack = controller.mqtt.publish.call_args_list[-1][0][1]
    assert ack["ok"] is False


def test_actuator_command_refuses_unknown_target(controller):
    controller._on_message(topic("actuators"), cmd_payload("on", target="Nope"))
    controller.actuators["Pump"].on.assert_not_called()
    assert controller.mqtt.publish.call_args_list[-1][0][1]["ok"] is False


def test_actuator_command_refuses_missing_target(controller):
    controller._on_message(topic("actuators"), cmd_payload("on"))
    controller.actuators["Pump"].on.assert_not_called()
    assert controller.mqtt.publish.call_args_list[-1][0][1]["ok"] is False


# --- commandes de capteurs ---------------------------------------------------


def test_sensor_command_publishes_reading(controller):
    controller.sensors["Soil"].read.return_value = {"moisture": {"value": 50.0}}
    controller._on_message(topic("sensors"), cmd_payload("read", target="Soil"))
    controller.sensors["Soil"].read.assert_called_once()
    telemetry = controller.mqtt.publish.call_args_list[0][0]
    assert telemetry[0] == f"growhub/v1/{DEVICE}/telemetry"
    assert telemetry[1] == {
        "seq": 1,
        "sensors": {"Soil": {"moisture": {"value": 50.0}}},
    }


def test_sensor_command_acks_the_reading(controller):
    controller.sensors["Soil"].read.return_value = {"moisture": {"value": 50.0}}
    controller._on_message(topic("sensors"), cmd_payload("read", target="Soil"))
    ack = controller.mqtt.publish.call_args_list[-1][0][1]
    assert ack["ok"] is True
    assert ack["state"] == {"sensors": {"Soil": {"moisture": {"value": 50.0}}}}


def test_sensor_command_reports_failed_read(controller):
    controller.sensors["Soil"].read.return_value = None
    controller._on_message(topic("sensors"), cmd_payload("read", target="Soil"))
    assert len(controller.mqtt.publish.call_args_list) == 1
    assert controller.mqtt.publish.call_args_list[0][0][1]["ok"] is False


def test_sensor_command_refuses_unknown_sensor(controller):
    controller._on_message(topic("sensors"), cmd_payload("read", target="Nope"))
    assert controller.mqtt.publish.call_args_list[0][0][1]["ok"] is False


# --- configuration ----------------------------------------------------------


def test_config_command_applies_interval(controller):
    controller._on_message(topic("config"), cmd_payload("set", telemetry_interval=60))
    assert controller.telemetry_interval == 60
    assert controller.mqtt.publish.call_args_list[-1][0][1]["ok"] is True


def test_config_command_publishes_retained_config(controller):
    controller._on_message(topic("config"), cmd_payload("set", telemetry_interval=60))
    state_call = controller.mqtt.publish.call_args_list[0][0]
    assert state_call[0] == f"growhub/v1/{DEVICE}/state"
    assert state_call[1] == {"config": {"telemetry_interval": 60}}


def test_config_command_refuses_interval_below_minimum(controller):
    controller._on_message(topic("config"), cmd_payload("set", telemetry_interval=1))
    assert controller.telemetry_interval == 30
    assert controller.mqtt.publish.call_args_list[-1][0][1]["ok"] is False


def test_config_command_refuses_unknown_key(controller):
    controller._on_message(topic("config"), cmd_payload("set", reboot_at="midi"))
    assert controller.mqtt.publish.call_args_list[-1][0][1]["ok"] is False


def test_config_command_refuses_unknown_action(controller):
    controller._on_message(topic("config"), cmd_payload("wipe"))
    assert controller.mqtt.publish.call_args_list[-1][0][1]["ok"] is False


# --- robustesse du routage ---------------------------------------------------


def test_unknown_topic_ignored(controller):
    controller._on_message(
        b"growhub/v1/ghb-bbbbbb/cmd/actuators",
        raw(cmd_payload("on", target="Pump")),
    )
    controller.mqtt.publish.assert_not_called()


def test_topic_of_another_device_ignored(controller):
    controller._on_message(topic("nonsense"), raw(cmd_payload("on", target="Pump")))
    controller.mqtt.publish.assert_not_called()


def test_malformed_payload_does_not_raise(controller):
    controller._on_message(topic("actuators"), b"{pas du json")
    controller.actuators["Pump"].on.assert_not_called()


# --- appairage ---------------------------------------------------------------


def test_credentials_message_is_saved_and_device_restarts(unpaired):
    _machine.reset.reset_mock()
    payload = {
        "username": DEVICE,
        "password": "device-pw",
        "broker": "broker",
        "port": 1883,
    }
    unpaired._on_message(f"growhub/v1/provision/{DEVICE}/creds".encode(), raw(payload))
    _machine.reset.assert_called_once()


def test_credentials_message_writes_the_file(tmp_path):
    path = Path(_creds_path(tmp_path))
    c = GrowHubController(MANIFEST, SECRETS, credentials_path=str(path))
    payload = {
        "username": DEVICE,
        "password": "device-pw",
        "broker": "broker",
        "port": 1883,
    }
    c._on_message(f"growhub/v1/provision/{DEVICE}/creds", raw(payload))
    assert _json.loads(path.read_text())["username"] == DEVICE
    assert _json.loads(path.read_text())["password"] == "device-pw"


def test_credentials_message_ignored_once_paired(controller):
    controller._on_message(
        f"growhub/v1/provision/{DEVICE}/creds",
        raw({"username": "ghb-x", "password": "y"}),
    )
    # Un boîtier appairé ne se réappaire pas tout seul sur ce topic.
    controller.mqtt.publish.assert_not_called()


def test_incomplete_credentials_are_ignored(unpaired):
    _machine.reset.reset_mock()
    unpaired._on_message(
        f"growhub/v1/provision/{DEVICE}/creds", raw({"username": DEVICE})
    )
    _machine.reset.assert_not_called()


# --- boucles -----------------------------------------------------------------


def test_telemetry_task_publishes_sequence(controller):
    controller.wifi.wlan.isconnected.return_value = True
    controller.mqtt.is_connected.return_value = True
    controller.sensors["Soil"].read.return_value = {"moisture": {"value": 42.0}}
    controller.sensors["Climate"].read.return_value = {"temperature": {"value": 20}}
    controller.actuators["Pump"].is_on.return_value = True

    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(controller._telemetry_task())

    controller.mqtt.publish.assert_called_once()
    published_topic, data = controller.mqtt.publish.call_args[0]
    assert published_topic == f"growhub/v1/{DEVICE}/telemetry"
    assert data["seq"] == 1
    assert data["sensors"]["Soil"] == {"moisture": {"value": 42.0}}
    assert data["sensors"]["Climate"] == {"temperature": {"value": 20}}
    assert data["actuators"] == {"Pump": "OFF"}
    assert "ts" not in data


def test_telemetry_task_skips_failed_sensor(controller):
    controller.wifi.wlan.isconnected.return_value = True
    controller.mqtt.is_connected.return_value = True
    controller.sensors["Soil"].read.return_value = None
    controller.sensors["Climate"].read.return_value = {"temperature": {"value": 20}}

    async def break_on_interval(delay):
        # Distingue le sommeil d'intervalle des attentes de réessai (2 s).
        if delay == controller.telemetry_interval:
            raise _LoopBreak()

    with patch("asyncio.sleep", break_on_interval):
        with pytest.raises(_LoopBreak):
            asyncio.run(controller._telemetry_task())

    data = controller.mqtt.publish.call_args[0][1]
    assert data["sensors"] == {"Climate": {"temperature": {"value": 20}}}


def test_telemetry_task_uses_the_configured_interval(controller):
    controller.wifi.wlan.isconnected.return_value = True
    controller.mqtt.is_connected.return_value = True
    controller.telemetry_interval = 120
    sleeps = []

    async def record_sleep(delay):
        sleeps.append(delay)
        raise _LoopBreak()

    with patch("asyncio.sleep", record_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(controller._telemetry_task())
    assert sleeps == [120]


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


def test_mqtt_keepalive_reconnects_and_announces(controller):
    controller.wifi.wlan.isconnected.return_value = True
    controller.mqtt.is_connected.return_value = False
    controller.mqtt.connect = AsyncMock(return_value=True)
    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(controller._mqtt_keepalive())
    controller.mqtt.connect.assert_called_once()


def test_announce_publishes_info_and_state(controller):
    controller._announce()
    published = [call[0][0] for call in controller.mqtt.publish.call_args_list]
    assert f"growhub/v1/{DEVICE}/info" in published
    assert f"growhub/v1/{DEVICE}/state" in published
    info_call = [
        call
        for call in controller.mqtt.publish.call_args_list
        if call[0][0] == f"growhub/v1/{DEVICE}/info"
    ][0]
    payload = info_call[0][1]
    assert payload["hw_id"] == DEVICE
    assert payload["sensors"] == [{"name": "Soil"}, {"name": "Climate"}]
    assert payload["actuators"] == [{"name": "Pump"}]
    assert payload["fw"] == "2.0.0"
    assert payload["model"] == "Bourgeon V1"


def test_unpaired_device_announces_itself_for_pairing(unpaired):
    unpaired._announce()
    published = [call[0][0] for call in unpaired.mqtt.publish.call_args_list]
    assert f"growhub/v1/provision/{DEVICE}" in published


def test_paired_device_does_not_announce_pairing(controller):
    controller._announce()
    published = [call[0][0] for call in controller.mqtt.publish.call_args_list]
    assert f"growhub/v1/provision/{DEVICE}" not in published


# --- affichage ---------------------------------------------------------------


def test_setup_display_when_configured(tmp_path):
    display_module = sys.modules["src.display"]
    display_module.Display.reset_mock()
    c = GrowHubController(MANIFEST, SECRETS, credentials_path=_creds_path(tmp_path))
    assert c.display is display_module.Display.return_value
    display_module.Display.assert_called_once_with(DISPLAY_CONFIG)
    # L'écran sait quoi montrer à partir du seul manifeste.
    assert c.screen.per_page == 2


def test_setup_display_absent(tmp_path):
    without_display = {k: v for k, v in MANIFEST.items() if k != "display"}
    c = GrowHubController(
        without_display, SECRETS, credentials_path=_creds_path(tmp_path)
    )
    assert c.display is None
    assert c.screen is None


def test_display_task_returns_when_no_display(tmp_path):
    without_display = {k: v for k, v in MANIFEST.items() if k != "display"}
    c = GrowHubController(
        without_display, SECRETS, credentials_path=_creds_path(tmp_path)
    )
    asyncio.run(c._display_task())


def test_display_task_shows_pairing_code(unpaired):
    unpaired.display = MagicMock()
    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(unpaired._display_task())
    unpaired.display.text.assert_any_call("BOURGEON", 0, 0)
    unpaired.display.text.assert_any_call("Code : ABC234", 0, 20)
    unpaired.display.text.assert_any_call(DEVICE, 0, 40)
    unpaired.display.show.assert_called_once()


def test_display_task_renders_the_manifest_fields(controller):
    """Les champs viennent du manifeste : le contrôleur ignore ce qu'il affiche."""
    controller.display = MagicMock()
    controller.sensors["Climate"].read.return_value = {
        "temperature": {"value": 21.5, "unit": "celsius"},
        "humidity": {"value": 55, "unit": "percent"},
    }
    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(controller._display_task())

    controller.display.clear.assert_called_once()
    controller.display.text.assert_any_call("BOURGEON", 0, 0)
    controller.display.text.assert_any_call("Temp: 21.5 °C", 0, 20)
    controller.display.text.assert_any_call("Hum: 55 %", 0, 40)
    controller.display.show.assert_called_once()


def test_display_task_shows_a_dash_for_a_missing_measure(controller):
    # Un capteur muet n'efface plus tout l'écran : seule sa ligne manque.
    controller.display = MagicMock()
    for sensor in controller.sensors.values():
        sensor.read.return_value = {"moisture": {"value": 40, "unit": "percent"}}
    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(controller._display_task())
    controller.display.text.assert_any_call("Temp: --", 0, 20)
    controller.display.text.assert_any_call("Hum: --", 0, 40)
    controller.display.text.assert_any_call("BOURGEON", 0, 0)


def test_display_task_follows_an_explicit_field_list(tmp_path):
    manifest = dict(
        MANIFEST,
        display=dict(
            DISPLAY_CONFIG,
            fields=[
                {
                    "source": "Soil",
                    "metric": "moisture",
                    "label": "Sol",
                    "decimals": 0,
                },
                {"kind": "actuator", "source": "Pump", "label": "Pompe"},
            ],
        ),
    )
    creds = Path(_creds_path(tmp_path))
    creds.write_text(_json.dumps(STORED_CREDENTIALS))  # boîtier appairé
    c = GrowHubController(manifest, SECRETS, credentials_path=str(creds))
    c.display = MagicMock()
    c.sensors["Soil"].read.return_value = {
        "moisture": {"value": 42.4, "unit": "percent"}
    }
    c.actuators["Pump"].human_state.return_value = "ON"

    with patch("asyncio.sleep", _break_sleep):
        with pytest.raises(_LoopBreak):
            asyncio.run(c._display_task())

    c.display.text.assert_any_call("Sol: 42 %", 0, 20)
    c.display.text.assert_any_call("Pompe: Allumé", 0, 40)


# --- lectures capteurs -------------------------------------------------------


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


def test_read_sensor_recovers_from_exception(controller):
    sensor = controller.sensors["Soil"]
    sensor.read.side_effect = [OSError("fail"), {"moisture": {"value": 5}}]
    with patch("asyncio.sleep", _instant_sleep):
        result = asyncio.run(controller._read_sensor(sensor))
    assert result == {"moisture": {"value": 5}}
    assert sensor.read.call_count == 2
