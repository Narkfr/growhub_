import sys
import types
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# --- Fake third-party modules ------------------------------------------------
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

_psycopg2 = types.ModuleType("psycopg2")
_psycopg2.connect = MagicMock()
_psycopg2.DatabaseError = type("DatabaseError", (Exception,), {})
sys.modules["psycopg2"] = _psycopg2

_aps = types.ModuleType("apscheduler")
_aps.__path__ = []
_aps_sched = types.ModuleType("apscheduler.schedulers")
_aps_sched.__path__ = []
_aps_bg = types.ModuleType("apscheduler.schedulers.background")
_aps_bg.BackgroundScheduler = MagicMock()
sys.modules["apscheduler"] = _aps
sys.modules["apscheduler.schedulers"] = _aps_sched
sys.modules["apscheduler.schedulers.background"] = _aps_bg

_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = MagicMock()
sys.modules["dotenv"] = _dotenv

from gateway import logic_engine  # noqa: E402

_BASE = datetime(2026, 1, 1, 0, 0, 0)


class FakeDateTime:
    """Controllable clock whose ``now()`` returns a fixed hour of a fixed day."""

    def __init__(self, hour):
        self.dt = _BASE.replace(hour=hour)

    def now(self):
        return self.dt


@pytest.fixture(autouse=True)
def _reset_state():
    logic_engine._actuator_state.clear()
    logic_engine._actuator_changed_at.clear()
    logic_engine.mqtt_client.publish.reset_mock()
    yield


# --- send_command ------------------------------------------------------------


def test_send_command_publishes_on_action_topic():
    logic_engine.send_command("dev1", "Pump", "on")
    logic_engine.mqtt_client.publish.assert_called_once_with(
        "dev1/actuators/Pump/action", "on"
    )


# --- set_actuator ------------------------------------------------------------


def test_set_actuator_sends_on_state_change():
    logic_engine.set_actuator("dev1", "Pump", "on")
    logic_engine.mqtt_client.publish.assert_called_once_with(
        "dev1/actuators/Pump/action", "on"
    )


def test_set_actuator_skips_same_state():
    logic_engine.set_actuator("dev1", "Pump", "on")
    logic_engine.mqtt_client.publish.reset_mock()
    logic_engine.set_actuator("dev1", "Pump", "on")
    logic_engine.mqtt_client.publish.assert_not_called()


def test_set_actuator_skips_none():
    logic_engine.set_actuator("dev1", "Pump", None)
    logic_engine.mqtt_client.publish.assert_not_called()


def test_set_actuator_min_run_blocks_early_off():
    logic_engine.set_actuator("dev1", "Pump", "on")
    logic_engine.mqtt_client.publish.reset_mock()
    logic_engine.set_actuator("dev1", "Pump", "off")  # < MIN_RUN_SECONDS
    logic_engine.mqtt_client.publish.assert_not_called()


def test_set_actuator_off_after_min_run():
    logic_engine.set_actuator("dev1", "Pump", "on")
    logic_engine._actuator_changed_at[("dev1", "Pump")] = datetime.now() - timedelta(
        seconds=60
    )
    logic_engine.mqtt_client.publish.reset_mock()
    logic_engine.set_actuator("dev1", "Pump", "off")
    logic_engine.mqtt_client.publish.assert_called_once_with(
        "dev1/actuators/Pump/action", "off"
    )


# --- handle_moisture ---------------------------------------------------------


def test_handle_moisture_below_target_turns_on():
    logic_engine.handle_moisture("dev1", {"moisture_target": 50}, 40)
    logic_engine.mqtt_client.publish.assert_called_once_with(
        "dev1/actuators/WaterPump/action", "on"
    )


def test_handle_moisture_above_hysteresis_turns_off():
    logic_engine._actuator_state[("dev1", "WaterPump")] = "on"
    logic_engine._actuator_changed_at[("dev1", "WaterPump")] = (
        datetime.now() - timedelta(seconds=60)
    )
    logic_engine.mqtt_client.publish.reset_mock()
    logic_engine.handle_moisture("dev1", {"moisture_target": 50}, 60)
    logic_engine.mqtt_client.publish.assert_called_once_with(
        "dev1/actuators/WaterPump/action", "off"
    )


def test_handle_moisture_in_hysteresis_band_does_nothing():
    logic_engine.handle_moisture("dev1", {"moisture_target": 50}, 52)
    logic_engine.mqtt_client.publish.assert_not_called()


# --- handle_lighting ---------------------------------------------------------


def test_handle_lighting_turns_on_within_window():
    with patch.object(logic_engine, "datetime", FakeDateTime(8)):
        logic_engine.handle_lighting("dev1", {"light_start_hour": 7, "light_hours": 12})
    logic_engine.mqtt_client.publish.assert_called_once_with(
        "dev1/actuators/GrowLamp/action", "on"
    )


def test_handle_lighting_turns_off_outside_window():
    logic_engine._actuator_state[("dev1", "GrowLamp")] = "on"
    logic_engine._actuator_changed_at[("dev1", "GrowLamp")] = _BASE.replace(hour=20)
    logic_engine.mqtt_client.publish.reset_mock()
    with patch.object(logic_engine, "datetime", FakeDateTime(21)):
        logic_engine.handle_lighting("dev1", {"light_start_hour": 7, "light_hours": 12})
    logic_engine.mqtt_client.publish.assert_called_once_with(
        "dev1/actuators/GrowLamp/action", "off"
    )


def test_handle_lighting_overnight_span():
    # start 22h for 8h -> end 6h (spans midnight); 2h is inside.
    with patch.object(logic_engine, "datetime", FakeDateTime(2)):
        logic_engine.handle_lighting("dev1", {"light_start_hour": 22, "light_hours": 8})
    logic_engine.mqtt_client.publish.assert_called_once_with(
        "dev1/actuators/GrowLamp/action", "on"
    )


def test_handle_lighting_duration_zero_turns_off():
    logic_engine._actuator_state[("dev1", "GrowLamp")] = "on"
    logic_engine._actuator_changed_at[("dev1", "GrowLamp")] = _BASE.replace(hour=1)
    logic_engine.mqtt_client.publish.reset_mock()
    with patch.object(logic_engine, "datetime", FakeDateTime(2)):
        logic_engine.handle_lighting("dev1", {"light_hours": 0})
    logic_engine.mqtt_client.publish.assert_called_once_with(
        "dev1/actuators/GrowLamp/action", "off"
    )


# --- MQTT callbacks ----------------------------------------------------------


def test_on_connect_subscribes_on_success():
    client = MagicMock()
    logic_engine.on_connect(client, None, None, 0)
    client.subscribe.assert_called_once_with("+/telemetry")


def test_on_connect_does_not_subscribe_on_failure():
    client = MagicMock()
    logic_engine.on_connect(client, None, None, 1)
    client.subscribe.assert_not_called()


def _msg(topic, payload_json):
    msg = MagicMock()
    msg.topic = topic
    msg.payload = payload_json.encode()
    return msg


def test_on_message_moisture_triggers_watering():
    with patch.object(
        logic_engine,
        "get_active_device_config",
        return_value=({"moisture_target": 50}, "AUTO"),
    ):
        logic_engine.on_message(
            None,
            None,
            _msg("dev1/telemetry", '{"SoilSensor": {"moisture": {"value": 40}}}'),
        )
    logic_engine.mqtt_client.publish.assert_called_once_with(
        "dev1/actuators/WaterPump/action", "on"
    )


def test_on_message_no_config_skips():
    with patch.object(logic_engine, "get_active_device_config", return_value=None):
        logic_engine.on_message(
            None,
            None,
            _msg("dev1/telemetry", '{"SoilSensor": {"moisture": {"value": 40}}}'),
        )
    logic_engine.mqtt_client.publish.assert_not_called()


def test_on_message_manual_mode_skips():
    with patch.object(
        logic_engine,
        "get_active_device_config",
        return_value=({"moisture_target": 50}, "MANUAL"),
    ):
        logic_engine.on_message(
            None,
            None,
            _msg("dev1/telemetry", '{"SoilSensor": {"moisture": {"value": 40}}}'),
        )
    logic_engine.mqtt_client.publish.assert_not_called()
