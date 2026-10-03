import sys
import types
from unittest.mock import MagicMock

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

_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = MagicMock()
sys.modules["dotenv"] = _dotenv


class FakePoint:
    """Minimal InfluxDB Point stand-in that records tags and fields."""

    def __init__(self, name):
        self.name = name
        self.tags = {}
        self.fields = {}

    def tag(self, key, value):
        self.tags[key] = value
        return self

    def field(self, key, value):
        self.fields[key] = value
        return self


_influx = types.ModuleType("influxdb_client")
_influx.InfluxDBClient = MagicMock()
_influx.Point = FakePoint
_influx_client_pkg = types.ModuleType("influxdb_client.client")
_influx_client_pkg.__path__ = []
_influx_write_api = types.ModuleType("influxdb_client.client.write_api")
_influx_write_api.SYNCHRONOUS = "SYNCHRONOUS"
sys.modules["influxdb_client"] = _influx
sys.modules["influxdb_client.client"] = _influx_client_pkg
sys.modules["influxdb_client.client.write_api"] = _influx_write_api

from gateway import telemetry_logger  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_write():
    telemetry_logger.write_api.write.reset_mock()
    yield


def _last_record():
    return telemetry_logger.write_api.write.call_args.kwargs["record"]


# --- handle_sensors ----------------------------------------------------------


def test_handle_sensors_skips_actuators_and_none():
    telemetry_logger.handle_sensors(
        "dev1", {"actuators": {"Pump": "ON"}, "Climate": None}
    )
    telemetry_logger.write_api.write.assert_not_called()


def test_handle_sensors_writes_fields():
    telemetry_logger.handle_sensors(
        "dev1",
        {
            "Soil": {"moisture": {"value": 42.0, "unit": "percent"}},
            "Climate": {
                "temperature": {"value": 20, "unit": "celsius"},
                "humidity": {"value": 50, "unit": "percent"},
            },
        },
    )
    assert telemetry_logger.write_api.write.call_count == 2
    soil_call = telemetry_logger.write_api.write.call_args_list[0]
    rec = soil_call.kwargs["record"]
    assert soil_call.kwargs["bucket"] == telemetry_logger.INFLUX_BUCKET
    assert rec.tags == {"device": "dev1", "sensor": "Soil"}
    assert rec.fields == {"moisture": 42.0}


def test_handle_sensors_skips_non_numeric_field():
    telemetry_logger.handle_sensors(
        "dev1", {"Climate": {"temperature": {"value": "not-a-number"}}}
    )
    assert _last_record().fields == {}


def test_handle_sensors_accepts_plain_value():
    telemetry_logger.handle_sensors("dev1", {"Soil": {"moisture": 33}})
    assert _last_record().fields == {"moisture": 33.0}


# --- handle_actuator_event ---------------------------------------------------


def test_handle_actuator_event_on():
    telemetry_logger.handle_actuator_event("dev1", "Pump", {"state": "ON"})
    rec = _last_record()
    assert rec.name == "actuators_events"
    assert rec.tags["actuator"] == "Pump"
    assert rec.fields["state"] == 1


def test_handle_actuator_event_default_off():
    telemetry_logger.handle_actuator_event("dev1", "Pump", {})
    assert _last_record().fields["state"] == 0


# --- handle_device_status ----------------------------------------------------


def test_handle_device_status_online():
    telemetry_logger.handle_device_status("dev1", b"online")
    rec = _last_record()
    assert rec.name == "device_status"
    assert rec.fields["online"] == 1


def test_handle_device_status_offline_with_whitespace():
    telemetry_logger.handle_device_status("dev1", b"  OFFLINE\n")
    assert _last_record().fields["online"] == 0


# --- on_message routing ------------------------------------------------------


def _msg(topic, payload_bytes):
    msg = MagicMock()
    msg.topic = topic
    msg.payload = payload_bytes
    return msg


def test_on_message_status_route():
    telemetry_logger.on_message(None, None, _msg("dev1/status", b"online"))
    assert _last_record().name == "device_status"


def test_on_message_telemetry_route():
    telemetry_logger.on_message(
        None, None, _msg("dev1/telemetry", b'{"Soil": {"moisture": {"value": 30.0}}}')
    )
    assert _last_record().name == "environment"


def test_on_message_data_route():
    telemetry_logger.on_message(
        None, None, _msg("dev1/data/Pump/state", b'{"state": "ON"}')
    )
    rec = _last_record()
    assert rec.name == "actuators_events"
    assert rec.tags["actuator"] == "Pump"
