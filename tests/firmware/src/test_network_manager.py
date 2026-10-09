import asyncio
import sys
import types
from unittest.mock import MagicMock

import pytest


async def _noop_sleep(_seconds):
    return None


_network = MagicMock()
_network.STA_IF = 0
sys.modules["network"] = _network

_uasyncio = types.ModuleType("uasyncio")
_uasyncio.sleep = _noop_sleep
sys.modules["uasyncio"] = _uasyncio

from firmware.src.network_manager import NetworkManager  # noqa: E402


@pytest.fixture
def wlan():
    return _network.WLAN.return_value


@pytest.fixture(autouse=True)
def _reset(wlan):
    _network.WLAN.reset_mock()
    wlan.reset_mock(return_value=True, side_effect=True)
    yield


def test_init_activates_wlan(wlan):
    NetworkManager("ssid", "pw")
    _network.WLAN.assert_called_once_with(_network.STA_IF)
    wlan.active.assert_called_once_with(True)


def test_connect_when_already_connected(wlan):
    wlan.isconnected.return_value = True
    wlan.ifconfig.return_value = ("192.168.1.10",)
    nm = NetworkManager("ssid", "pw")
    assert asyncio.run(nm.connect()) is True
    wlan.connect.assert_not_called()


def test_connect_success_after_attempts(wlan):
    wlan.isconnected.side_effect = [False, False, False, True, True]
    wlan.ifconfig.return_value = ("192.168.1.10",)
    nm = NetworkManager("ssid", "pw")
    assert asyncio.run(nm.connect()) is True
    wlan.connect.assert_called_once_with("ssid", "pw")


def test_connect_timeout_returns_false(wlan):
    wlan.isconnected.return_value = False
    nm = NetworkManager("ssid", "pw")
    assert asyncio.run(nm.connect()) is False
    wlan.connect.assert_called_once_with("ssid", "pw")
