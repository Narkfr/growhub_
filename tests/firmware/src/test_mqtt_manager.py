import asyncio
import json as _json
import sys
import types
from unittest.mock import MagicMock

import pytest

# --- Fake MicroPython modules -------------------------------------------------
_ujson = types.ModuleType("ujson")
_ujson.dumps = _json.dumps
_ujson.loads = _json.loads
sys.modules["ujson"] = _ujson

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

from firmware.src.mqtt_manager import MqttManager  # noqa: E402


@pytest.fixture
def client_cls():
    _simple.MQTTClient.reset_mock(return_value=True)
    return _simple.MQTTClient


@pytest.fixture
def manager(client_cls):
    return MqttManager("dev1", "broker.local", "user", "pass", port=1883)


def test_init_builds_client(client_cls, manager):
    client_cls.assert_called_once_with(
        client_id="dev1",
        server="broker.local",
        user="user",
        password="pass",
        port=1883,
        keepalive=60,
    )


def test_init_defaults_and_subscriptions(manager):
    assert manager.connected is False
    assert manager.broker_ip == "broker.local"
    assert manager.subscriptions == [
        "dev1/actuators/+/action",
        "dev1/sensors/+/action",
    ]
    assert manager.status_topic == "dev1/status"


def test_is_connected(manager):
    assert manager.is_connected() is False
    manager.connected = True
    assert manager.is_connected() is True


def test_set_callback(manager):
    cb = lambda topic, msg: None  # noqa: E731
    manager.set_callback(cb)
    manager.client.set_callback.assert_called_once_with(cb)


def test_disconnect_closes_and_marks_disconnected(manager):
    manager.connected = True
    manager.disconnect()
    manager.client.disconnect.assert_called_once()
    assert manager.connected is False


def test_disconnect_swallows_socket_errors(manager):
    manager.client.disconnect.side_effect = OSError("boom")
    manager.disconnect()
    assert manager.connected is False


def test_connect_success_sets_will_and_subscribes(manager):
    result = asyncio.run(manager.connect())
    assert result is True
    assert manager.connected is True
    manager.client.set_last_will.assert_called_once_with(
        "dev1/status", b"offline", retain=True
    )
    assert manager.client.connect.call_count == 1
    assert manager.client.subscribe.call_count == 2
    manager.client.subscribe.assert_any_call("dev1/actuators/+/action")
    manager.client.subscribe.assert_any_call("dev1/sensors/+/action")
    manager.client.publish.assert_called_once_with(
        "dev1/status", b"online", retain=True
    )


def test_connect_failure_marks_disconnected(manager):
    manager.client.connect.side_effect = OSError("refused")
    result = asyncio.run(manager.connect())
    assert result is False
    assert manager.connected is False


def test_check_msg_marks_disconnected_on_error(manager):
    manager.connected = True
    manager.client.check_msg.side_effect = OSError("closed")
    manager.check_msg()
    assert manager.connected is False


def test_check_msg_keeps_connected(manager):
    manager.connected = True
    manager.check_msg()
    assert manager.connected is True


def test_publish_json(manager):
    manager.publish("dev1/telemetry", {"a": 1})
    manager.client.publish.assert_called_once_with(
        "dev1/telemetry", '{"a": 1}', retain=False, qos=0
    )


def test_publish_with_retain_and_qos(manager):
    manager.publish("t", {"x": 2}, retain=True, qos=1)
    manager.client.publish.assert_called_once_with("t", '{"x": 2}', retain=True, qos=1)


def test_publish_failure_marks_disconnected(manager):
    manager.connected = True
    manager.client.publish.side_effect = OSError("closed")
    manager.publish("t", {"a": 1})
    assert manager.connected is False
