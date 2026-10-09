import asyncio
import sys

import pytest

# Les faux modules MicroPython viennent de tests/firmware/conftest.py.
_simple = sys.modules["lib.umqtt.simple"]

from firmware.src.mqtt_manager import MqttManager  # noqa: E402

DEVICE = "ghb-3f2a91"


@pytest.fixture
def client_cls():
    _simple.MQTTClient.reset_mock(return_value=True)
    return _simple.MQTTClient


@pytest.fixture
def manager(client_cls):
    return MqttManager(DEVICE, "broker.local", "ghb-3f2a91", "pass", port=1883)


def test_init_uses_the_device_id_as_broker_identity(client_cls, manager):
    # L'identité broker EST l'identifiant du boîtier : c'est ce que le motif %u
    # des ACL utilise pour cloisonner les appareils.
    client_cls.assert_called_once_with(
        client_id=DEVICE,
        server="broker.local",
        user="ghb-3f2a91",
        password="pass",
        port=1883,
        keepalive=60,
    )


def test_init_defaults(manager):
    assert manager.connected is False
    assert manager.broker_ip == "broker.local"
    assert manager.status_topic == "growhub/v1/ghb-3f2a91/status"


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


def test_connect_subscribes_to_the_device_command_topics(manager):
    result = asyncio.run(manager.connect())
    assert result is True
    assert manager.connected is True
    manager.client.set_last_will.assert_called_once_with(
        f"growhub/v1/{DEVICE}/status", b"offline", retain=True
    )
    assert manager.client.connect.call_count == 1
    assert manager.client.subscribe.call_count == 3
    manager.client.subscribe.assert_any_call(f"growhub/v1/{DEVICE}/cmd/actuators")
    manager.client.subscribe.assert_any_call(f"growhub/v1/{DEVICE}/cmd/sensors")
    manager.client.subscribe.assert_any_call(f"growhub/v1/{DEVICE}/cmd/config")
    manager.client.publish.assert_called_once_with(
        f"growhub/v1/{DEVICE}/status", b"online", retain=True
    )


def test_connect_accepts_extra_subscriptions(manager):
    extra = f"growhub/v1/provision/{DEVICE}/creds"
    asyncio.run(manager.connect([extra]))
    manager.client.subscribe.assert_called_once_with(extra)


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
    assert manager.publish("growhub/v1/ghb-3f2a91/telemetry", {"a": 1}) is True
    manager.client.publish.assert_called_once_with(
        "growhub/v1/ghb-3f2a91/telemetry", '{"a": 1}', retain=False, qos=0
    )


def test_publish_with_retain_and_qos(manager):
    manager.publish("t", {"x": 2}, retain=True, qos=1)
    manager.client.publish.assert_called_once_with("t", '{"x": 2}', retain=True, qos=1)


def test_publish_accepts_pre_encoded_payload(manager):
    # Le testament est publié en octets bruts : la charge utile ne doit pas être
    # re-encodée en JSON.
    manager.publish("t", b"offline", retain=True)
    manager.client.publish.assert_called_once_with("t", b"offline", retain=True, qos=0)


def test_publish_failure_marks_disconnected(manager):
    manager.connected = True
    manager.client.publish.side_effect = OSError("closed")
    assert manager.publish("t", {"a": 1}) is False
    assert manager.connected is False
