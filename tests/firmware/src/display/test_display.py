import sys
import types
from unittest.mock import MagicMock

import pytest

_machine = types.ModuleType("machine")
_machine.I2C = MagicMock()
_machine.Pin = MagicMock()
sys.modules["machine"] = _machine

_lib = types.ModuleType("lib")
_lib.__path__ = []
_ssd1306 = types.ModuleType("lib.ssd1306")
_ssd1306.SSD1306_I2C = MagicMock()
sys.modules["lib"] = _lib
sys.modules["lib.ssd1306"] = _ssd1306

from firmware.src.display import Display  # noqa: E402


@pytest.fixture
def display():
    _machine.I2C.reset_mock()
    _machine.Pin.reset_mock()
    _ssd1306.SSD1306_I2C.reset_mock()
    return Display({})


def test_init_uses_default_pins_and_size(display):
    _machine.Pin.assert_any_call(5)  # scl
    _machine.Pin.assert_any_call(4)  # sda
    _machine.I2C.assert_called_once_with(
        0,
        scl=_machine.Pin.return_value,
        sda=_machine.Pin.return_value,
        freq=400000,
    )
    _ssd1306.SSD1306_I2C.assert_called_once_with(
        128, 64, _machine.I2C.return_value, addr=0x3C
    )


def test_init_custom_i2c_pins_and_size():
    _machine.I2C.reset_mock()
    _machine.Pin.reset_mock()
    _ssd1306.SSD1306_I2C.reset_mock()
    Display(
        {
            "width": 96,
            "height": 32,
            "i2c": {"id": 1, "sda": 2, "scl": 3, "freq": 100000},
            "addr": 0x3D,
        }
    )
    _machine.I2C.assert_called_once_with(
        1,
        scl=_machine.Pin.return_value,
        sda=_machine.Pin.return_value,
        freq=100000,
    )
    _ssd1306.SSD1306_I2C.assert_called_once_with(
        96, 32, _machine.I2C.return_value, addr=0x3D
    )


def test_clear_fills_buffer(display):
    display.clear()
    _ssd1306.SSD1306_I2C.return_value.fill.assert_called_once_with(0)


def test_text_draws_string(display):
    display.text("hello", 10, 20)
    _ssd1306.SSD1306_I2C.return_value.text.assert_called_once_with("hello", 10, 20, 1)


def test_show_pushes_buffer(display):
    display.show()
    _ssd1306.SSD1306_I2C.return_value.show.assert_called_once()
